/* Tuckcard card engine.
 *
 * The reference implementation of the fit plan. render_core.py is the second
 * implementation; tools/parity/run.py compares the two and fails the build when
 * a line break or a final font size differs.
 *
 * Each template calls Tuckcard.render(card, style, format) and reads the fit data
 * from window.__report. The same boxes are drawn by render_pillow.py, so the two
 * renderers agree by design, not by luck.
 */
(function (global) {
  "use strict";

  var CARD_PX = 480;
  var PPI = 96;

  // ---------------------------------------------------------------- seeded random
  function imul(a, b) { return Math.imul(a | 0, b | 0); }

  function mulberry32(seed) {
    var a = seed | 0;
    return function () {
      a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function markSeed(cardN, lineIndex, kind) {
    return (cardN * 1000 + lineIndex * 17 + (kind || 0) * 101) & 0xFFFFFFFF;
  }

  // ---------------------------------------------------------------- shapes
  function catmull(points, samples) {
    samples = samples || 16;
    if (points.length < 3) return points.slice();
    var pts = [points[0]].concat(points, [points[points.length - 1]]);
    var out = [];
    for (var i = 1; i < pts.length - 2; i++) {
      var p0 = pts[i - 1], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2];
      for (var s = 0; s < samples; s++) {
        var t = s / samples, t2 = t * t, t3 = t * t * t;
        var x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t +
          (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
          (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3);
        var y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t +
          (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
          (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3);
        out.push([x, y]);
      }
    }
    out.push(points[points.length - 1]);
    return out;
  }

  function swashPoints(width, height, points, amplitude, seed, wobble) {
    var rnd = mulberry32(seed);
    var n = Math.max(3, points | 0);
    var base = [];
    for (var i = 0; i < n; i++) {
      var t = i / (n - 1);
      base.push([-2 + t * (width + 4),
        height * (0.35 + 0.35 * (4 * t * (1 - t))) + (rnd() * 2 - 1) * amplitude * wobble]);
    }
    return catmull(base);
  }

  function underlinePoints(width, amplitude, seed, wobble) {
    if (!amplitude || !wobble) return [[-2, 0], [width + 2, 0]];
    var rnd = mulberry32(seed);
    var pts = [];
    for (var i = 0; i < 5; i++) {
      var t = i / 4;
      pts.push([-2 + t * (width + 4), (rnd() * 2 - 1) * amplitude * wobble]);
    }
    return catmull(pts);
  }

  function highlightPolygon(x, top, bottom, width, inset, amplitude, points, seed, wobble) {
    var rnd = mulberry32(seed);
    var n = Math.max(2, points | 0);
    var tops = [], bottoms = [];
    for (var i = 0; i < n; i++) {
      var t = i / (n - 1);
      var px = x - inset + t * (width + 2 * inset);
      if (!wobble) {
        tops.push([px, top]); bottoms.push([px, bottom]);
      } else {
        tops.push([px, top + (rnd() * 2 - 1) * amplitude * wobble]);
        bottoms.push([px, bottom + (rnd() * 2 - 1) * amplitude * wobble]);
      }
    }
    return tops.concat(bottoms.reverse());
  }

  // ---------------------------------------------------------------- measurement
  var measurer = null;

  function measure(text, family, weight, size) {
    return Math.round(measureExact(text, family, weight, size));
  }

  var exactCache = {};

  function measureExact(text, family, weight, size) {
    ensureMeasurer();
    var key = family + "|" + weight + "|" + size + "|" + text;
    if (Object.prototype.hasOwnProperty.call(exactCache, key)) return exactCache[key];
    var span = document.createElement("span");
    span.textContent = text;
    span.style.cssText = "position:absolute;left:-9999px;top:0;white-space:pre;display:inline-block;" +
      "font-family:'" + family + "';font-weight:" + weight + ";" +
      "font-size:" + size + "px;line-height:1;font-kerning:none;" +
      "font-feature-settings:'kern' 0,'liga' 0;" + variationCss(family, weight);
    measurer.appendChild(span);
    var width = span.getBoundingClientRect().width;
    measurer.removeChild(span);
    exactCache[key] = width;
    return width;
  }

  function variationCss(family, weight) {
    var axes = {};
    if (family === "Fraunces") axes = { wght: weight, opsz: 40, SOFT: 0, WONK: 0 };
    else if (family === "Literata") axes = { wght: weight, opsz: 20 };
    else if (family === "Shantell Sans") axes = { wght: weight, BNCE: 0, INFM: 0, SPAC: 0 };
    else if (family === "Source Serif 4") axes = { wght: weight, opsz: 20 };
    else if (family === "Caveat") axes = { wght: weight };
    var parts = [];
    Object.keys(axes).forEach(function (k) {
      parts.push('"' + k + '" ' + axes[k]);
    });
    return parts.length ? "font-variation-settings:" + parts.join(",") + ";" : "";
  }

  /* Load every face before planning. document.fonts.ready resolves even when
     no face has been requested yet, so measuring first would silently use a
     fallback font and wrap differently from Pillow. */
  function loadFonts() {
    if (!document.fonts) return Promise.resolve();
    var pending = [];
    document.fonts.forEach(function (face) {
      if (face.status !== "loaded") pending.push(face.load().catch(function () { return null; }));
    });
    return Promise.all(pending).then(function () { return document.fonts.ready; });
  }

  // ---------------------------------------------------------------- fit
  function region(layout, name) {
    var r = layout.regions[name];
    return { x: r.x_in * PPI, y: r.y_in * PPI, w: r.width_in * PPI, h: r.height_in * PPI };
  }

  function splitWords(text, target, occurrence) {
    var words = text.split(/\s+/).filter(Boolean);
    if (!target) return { words: words, span: null };
    var hay = words.join(" ");
    var start = -1;
    for (var k = 0; k < (occurrence || 1); k++) {
      start = hay.indexOf(target, start + 1);
      if (start < 0) return { words: words, span: null };
    }
    var end = start + target.length, pos = 0, spans = [];
    words.forEach(function (word) {
      spans.push([pos, pos + word.length]);
      pos += word.length + 1;
    });
    var first = -1, last = -1;
    spans.forEach(function (s, i) {
      if (s[0] <= start && start < s[1]) first = i;
      if (s[0] < end && end <= s[1]) last = i;
    });
    if (first < 0 || last < 0) return { words: words, span: null };
    return { words: words, span: [first, last + 1] };
  }

  function wrap(words, family, weight, size, maxWidth, glue, tailExtra, tailIndex) {
    // Decide on the exact width of the candidate line, the same rule as
    // render_core.py. Adding rounded word widths lets a fraction of a pixel
    // become a whole one and move a word to the next line. D-027.
    var lines = [], current = [];
    for (var i = 0; i < words.length; i++) {
      var candidate = current.concat([i]);
      var text = candidate.map(function (j) { return words[j]; }).join(" ");
      var width = measureExact(text, family, weight, size);
      if (tailIndex != null && candidate.indexOf(tailIndex) >= 0) width += (tailExtra || 0);
      if (current.length && !glue.has(i) && width > maxWidth) {
        lines.push(current); current = [i];
      } else {
        current = candidate;
      }
    }
    if (current.length) lines.push(current);
    return lines;
  }

  function lineRuns(words, indices, family, weight, size, markSpan, reserve) {
    reserve = reserve || 0;
    var space = measure(" ", family, weight, size);
    var first = indices[0], last = indices[indices.length - 1] + 1;
    var text = indices.map(function (i) { return words[i]; }).join(" ");
    var width = measure(text, family, weight, size);
    if (!markSpan) return { runs: [{ text: text, x: 0, width: width, marked: false }], width: width };
    var a = Math.max(first, markSpan[0]), b = Math.min(last, markSpan[1]);
    if (a >= b) return { runs: [{ text: text, x: 0, width: width, marked: false }], width: width };
    var runs = [], x = 0;
    if (a > first) {
      var pre = words.slice(first, a).join(" ");
      var pw = measure(pre, family, weight, size);
      runs.push({ text: pre, x: 0, width: pw, marked: false });
      x = pw + space;
    }
    var mid = words.slice(a, b).join(" ");
    var mw = measure(mid, family, weight, size);
    runs.push({ text: mid, x: x, width: mw, marked: true });
    x += mw + reserve;
    if (b < last) {
      x += space;
      var post = words.slice(b, last).join(" ");
      runs.push({ text: post, x: x, width: measure(post, family, weight, size), marked: false });
    }
    return { runs: runs, width: width + reserve };
  }

  function lineHasMark(indices, span) {
    return !!span && indices[0] < span[1] && indices[indices.length - 1] >= span[0];
  }

  function block(text, family, weight, size, maxWidth, lh) {
    var words = text.split(/\s+/).filter(Boolean);
    var lines = wrap(words, family, weight, size, maxWidth, new Set());
    var runs = [], widths = [];
    lines.forEach(function (indices, li) {
      var split = lineRuns(words, indices, family, weight, size, null, 0);
      split.runs.forEach(function (run) { run.row = li; runs.push(run); });
      widths.push(measure(indices.map(function (i) { return words[i]; }).join(" "), family, weight, size));
    });
    return { runs: runs, lines: lines.length, widths: widths };
  }

  // The title box must end before the next region starts. Both heights are
  // rounded to the whole pixel the block is drawn on, as render_core does, so
  // a two-line title that ends on the body's top edge touches it rather than
  // intruding. fits false means no size in the ladder fits, and the card fails.
  function fitTitle(card, layout, fonts, weights, maxWidth) {
    var family = fonts.title, weight = weights.title;
    var lh = layout.line_height.title;
    var words = card.title.split(/\s+/).filter(Boolean);
    var sizes = [layout.font_sizes.title].concat(layout.shrink_steps.title);
    var room = Math.round(region(layout, "title").h);
    for (var i = 0; i < sizes.length; i++) {
      var size = sizes[i];
      if (size < layout.font_floors.title) break;
      var lines = wrap(words, family, weight, size, maxWidth, new Set());
      if (Math.round(lines.length * size * lh) <= room) return { size: size, fits: true };
    }
    return { size: Math.max(layout.font_floors.title, sizes[sizes.length - 1]), fits: false };
  }

  function prepareLines(card, defaultStyle) {
    return card.lines.map(function (line, i) {
      var mark = line.mark || null;
      var split = splitWords(line.text, mark ? mark.target : null, mark && mark.occurrence);
      return {
        words: split.words, span: split.span, index: i,
        style: (mark && mark.style) || defaultStyle,
        note: line.note || null
      };
    });
  }

  function badgeReserve(style) {
    var p = style.marks.badge.params || {};
    return (p.diameter_px || 15) + (p.gap_px || 2);
  }

  function planStacked(card, style) {
    var layout = style.layout, fonts = style.fonts, weights = style.weights;
    var lh = layout.line_height, gaps = layout.gaps || {}, spacing = style.spacing || 1;
    var titleReg = region(layout, "title"), bodyReg = region(layout, "body");
    var titleFit = fitTitle(card, layout, fonts, weights, titleReg.w);
    var titleSize = titleFit.size;
    var titleBlock = block(card.title, fonts.title, weights.title, titleSize, titleReg.w, lh.title);
    var prepared = prepareLines(card, layout.mark_style || "swash");
    var chosen = null;
    var lineSizes = [layout.font_sizes.lines].concat(layout.shrink_steps.lines);
    var noteSizes = [layout.font_sizes.notes].concat(layout.shrink_steps.notes);
    for (var i = 0; i < lineSizes.length; i++) {
      if (lineSizes[i] < layout.font_floors.lines) break;
      for (var j = 0; j < noteSizes.length; j++) {
        if (noteSizes[j] < layout.font_floors.notes) break;
        var body = stackedBody(prepared, bodyReg, fonts, weights, lineSizes[i], noteSizes[j], lh, gaps, spacing);
        if (body.height <= bodyReg.h) { chosen = { ls: lineSizes[i], ns: noteSizes[j], body: body }; break; }
      }
      if (chosen) break;
    }
    var failed = !chosen || !titleFit.fits;
    if (failed) {
      var ls = layout.font_floors.lines;
      var ns = layout.font_floors.notes;
      chosen = { ls: ls, ns: ns, body: stackedBody(prepared, bodyReg, fonts, weights, ls, ns, lh, gaps, spacing) };
    }
    return {
      layout: "stacked", card: { w: CARD_PX, h: CARD_PX },
      labels: { header: headerText(card), watermark: String(card.n) },
      title: { x: titleReg.x, y: titleReg.y, runs: titleBlock.runs, size: titleSize,
        family: fonts.title, weight: weights.title, line_height: titleSize * lh.title,
        color: "var(--ink)" },
      body: { x: bodyReg.x, y: bodyReg.y, rows: chosen.body.rows, marks: chosen.body.marks,
        height: chosen.body.height },
      report: { sizes: { title: titleSize, lines: chosen.ls, notes: chosen.ns },
        shrunk: chosen.ls !== layout.font_sizes.lines || chosen.ns !== layout.font_sizes.notes || titleSize !== layout.font_sizes.title,
        failed: failed }
    };
  }

  function stackedBody(prepared, reg, fonts, weights, lineSize, noteSize, lh, gaps, spacing) {
    var x = reg.x, width = reg.w, cursor = reg.y, rows = [], marks = [];
    prepared.forEach(function (item) {
      var glue = new Set();
      if (item.span) for (var g = item.span[0] + 1; g < item.span[1]; g++) glue.add(g);
      var lines = wrap(item.words, fonts.lines, weights.lines, lineSize, width, glue);
      var lineH = lineSize * lh.lines;
      lines.forEach(function (indices) {
        var span = lineHasMark(indices, item.span) ? item.span : null;
        var split = lineRuns(item.words, indices, fonts.lines, weights.lines, lineSize, span, 0);
        rows.push({ kind: "text", x: x, y: cursor, height: lineH, size: lineSize,
          family: fonts.lines, weight: weights.lines, runs: split.runs });
        if (span) {
          marks.push({ style: item.style, line_index: item.index, runs: split.runs, x: x,
            y: cursor, height: lineH, size: lineSize, family: fonts.lines, weight: weights.lines });
        }
        cursor += lineH;
      });
      if (item.note) {
        var words = item.note.split(/\s+/).filter(Boolean);
        var indent = layoutIndent();
        var nlines = wrap(words, fonts.notes, weights.notes, noteSize, width - indent, new Set());
        var noteH = noteSize * lh.notes;
        nlines.forEach(function (indices) {
          var split = lineRuns(words, indices, fonts.notes, weights.notes, noteSize, null, 0);
          rows.push({ kind: "note", x: x + indent, y: cursor, height: noteH, size: noteSize,
            family: fonts.notes, weight: weights.notes, runs: split.runs });
          cursor += noteH;
        });
        cursor += (gaps.note || 0) * spacing;
      }
      cursor += (gaps.line || 0) * spacing;
    });
    return { rows: rows, marks: marks, height: cursor - reg.y };
  }

  var NOTE_INDENT = 18;
  function layoutIndent() { return NOTE_INDENT; }

  function planNotebook(card, style) {
    var layout = style.layout, fonts = style.fonts, weights = style.weights;
    var lh = layout.line_height;
    var regs = { title: region(layout, "title"), lines: region(layout, "lines"), notes: region(layout, "notes") };
    var titleFit = fitTitle(card, layout, fonts, weights, regs.title.w);
    var titleSize = titleFit.size;
    var titleBlock = block(card.title, fonts.title, weights.title, titleSize, regs.title.w, lh.title);
    var prepared = prepareLines(card, layout.mark_style || "highlight");
    var reserve = badgeReserve(style);
    var chosen = null;
    var lineSizes = [layout.font_sizes.lines].concat(layout.shrink_steps.lines);
    var noteSizes = [layout.font_sizes.notes].concat(layout.shrink_steps.notes);
    for (var i = 0; i < lineSizes.length; i++) {
      if (lineSizes[i] < layout.font_floors.lines) break;
      for (var j = 0; j < noteSizes.length; j++) {
        if (noteSizes[j] < layout.font_floors.notes) break;
        var body = notebookBody(prepared, regs, fonts, weights, lineSizes[i], noteSizes[j], lh, reserve);
        if (body.line_height <= regs.lines.h && body.note_height <= regs.notes.h) {
          chosen = { ls: lineSizes[i], ns: noteSizes[j], body: body }; break;
        }
      }
      if (chosen) break;
    }
    var failed = !chosen || !titleFit.fits;
    if (failed) {
      var ls = layout.font_floors.lines;
      var ns = layout.font_floors.notes;
      chosen = { ls: ls, ns: ns, body: notebookBody(prepared, regs, fonts, weights, ls, ns, lh, reserve) };
    }
    var titleLineH = titleSize * lh.title;
    var highlight = null;
    if (titleBlock.runs.length) {
      var lastRow = titleBlock.lines - 1;
      var words = card.title.split(/\s+/).filter(Boolean);
      var lastWord = words[words.length - 1];
      var wordW = measure(lastWord, fonts.title, weights.title, titleSize);
      var lineW = titleBlock.widths[lastRow];
      highlight = { x: regs.title.x + lineW - wordW - 2, y: regs.title.y + lastRow * titleLineH + 0.55 * titleLineH,
        w: wordW + 4, h: 0.45 * titleLineH };
    }
    return {
      layout: "notebook", card: { w: CARD_PX, h: CARD_PX },
      labels: { header: headerText(card), number: String(card.n) },
      title: { x: regs.title.x, y: regs.title.y, runs: titleBlock.runs, size: titleSize,
        family: fonts.title, weight: weights.title, line_height: titleLineH,
        color: "var(--ink)", highlight: highlight },
      body: { lines: chosen.body.lines, notes: chosen.body.notes, marks: chosen.body.marks,
        rule: { x: 30, w: 1.5 } },
      report: { sizes: { title: titleSize, lines: chosen.ls, notes: chosen.ns },
        shrunk: chosen.ls !== layout.font_sizes.lines || chosen.ns !== layout.font_sizes.notes || titleSize !== layout.font_sizes.title,
        failed: failed }
    };
  }

  function notebookBody(prepared, regs, fonts, weights, lineSize, noteSize, lh, reserve) {
    var lineH = lineSize * lh.lines, noteH = noteSize * lh.notes;
    var cursor = regs.lines.y, rows = [], notes = [], marks = [];
    var noteCursor = regs.notes.y, number = 0, maxLine = 0, maxNote = 0;
    prepared.forEach(function (item) {
      if (item.span) number += 1;
      var glue = new Set();
      if (item.span) for (var g = item.span[0] + 1; g < item.span[1]; g++) glue.add(g);
      var lines = wrap(item.words, fonts.lines, weights.lines, lineSize, regs.lines.w, glue,
        reserve, item.span ? item.span[1] - 1 : null);
      var rowStart = cursor;
      lines.forEach(function (indices) {
        var span = lineHasMark(indices, item.span) ? item.span : null;
        var split = lineRuns(item.words, indices, fonts.lines, weights.lines, lineSize, span, span ? reserve : 0);
        rows.push({ kind: "text", x: regs.lines.x, y: cursor, height: lineH, size: lineSize,
          family: fonts.lines, weight: weights.lines, runs: split.runs });
        if (span) {
          marks.push({ style: item.style, line_index: item.index, runs: split.runs,
            x: regs.lines.x, y: cursor, height: lineH, size: lineSize,
            family: fonts.lines, weight: weights.lines, number: number });
        }
        cursor += lineH;
      });
      if (item.note) {
        var prefix = item.span ? String(number) + "  " : "";
        var words = (prefix + item.note).split(/\s+/).filter(Boolean);
        var nlines = wrap(words, fonts.notes, weights.notes, noteSize, regs.notes.w, new Set());
        var ny = Math.max(rowStart, noteCursor);
        nlines.forEach(function (indices) {
          var split = lineRuns(words, indices, fonts.notes, weights.notes, noteSize, null, 0);
          notes.push({ kind: "note", x: regs.notes.x, y: ny, height: noteH, size: noteSize,
            family: fonts.notes, weight: weights.notes, runs: split.runs,
            number: item.span && ny === Math.max(rowStart, noteCursor) ? number : null });
          ny += noteH;
        });
        noteCursor = ny + 4;
        maxNote = Math.max(maxNote, noteCursor - regs.notes.y);
      }
      cursor += 9 * (lineSize / 18);
      maxLine = Math.max(maxLine, cursor - regs.lines.y);
    });
    return { lines: rows, notes: notes, marks: marks, line_height: maxLine, note_height: maxNote };
  }

  function planIndex(card, style) {
    var layout = style.layout, fonts = style.fonts, weights = style.weights;
    var lh = layout.line_height;
    var regs = { band: region(layout, "band"), title: region(layout, "title"),
      body: region(layout, "body"), notes: region(layout, "notes") };
    var titleFit = fitTitle(card, layout, fonts, weights, regs.title.w);
    var titleSize = titleFit.size;
    var titleBlock = block(card.title, fonts.title, weights.title, titleSize, regs.title.w, lh.title);
    var prepared = prepareLines(card, layout.mark_style || "underline");
    var reserve = badgeReserve(style);
    var chosen = null;
    var lineSizes = [layout.font_sizes.lines].concat(layout.shrink_steps.lines);
    var noteSizes = [layout.font_sizes.notes].concat(layout.shrink_steps.notes);
    for (var i = 0; i < lineSizes.length; i++) {
      if (lineSizes[i] < layout.font_floors.lines) break;
      for (var j = 0; j < noteSizes.length; j++) {
        if (noteSizes[j] < layout.font_floors.notes) break;
        var body = indexPart(prepared, regs, fonts, weights, lineSizes[i], noteSizes[j], lh, reserve);
        if (body.body_height <= regs.body.h && body.notes_height <= regs.notes.h) {
          chosen = { ls: lineSizes[i], ns: noteSizes[j], body: body }; break;
        }
      }
      if (chosen) break;
    }
    var failed = !chosen || !titleFit.fits;
    if (failed) {
      var ls = layout.font_floors.lines;
      var ns = layout.font_floors.notes;
      chosen = { ls: ls, ns: ns, body: indexPart(prepared, regs, fonts, weights, ls, ns, lh, reserve) };
    }
    return {
      layout: "index", card: { w: CARD_PX, h: CARD_PX },
      labels: { header: headerText(card), number: "No. " + card.n, try_this: "Try this" },
      band: { x: 0, y: 0, w: CARD_PX, h: regs.band.h },
      title: { x: regs.title.x, y: regs.title.y, runs: titleBlock.runs, size: titleSize,
        family: fonts.title, weight: weights.title, line_height: titleSize * lh.title,
        color: "var(--on-accent)" },
      body: { x: regs.body.x, y: regs.body.y, rows: chosen.body.body, height: chosen.body.body_height },
      notes: { x: regs.notes.x, y: regs.notes.y, rows: chosen.body.notes, height: chosen.body.notes_height },
      report: { sizes: { title: titleSize, lines: chosen.ls, notes: chosen.ns },
        shrunk: chosen.ls !== layout.font_sizes.lines || chosen.ns !== layout.font_sizes.notes || titleSize !== layout.font_sizes.title,
        failed: failed }
    };
  }

  function indexPart(prepared, regs, fonts, weights, lineSize, noteSize, lh, reserve) {
    var cursor = regs.body.y, body = [], notes = [], number = 0;
    prepared.forEach(function (item) {
      if (item.span) number += 1;
      var glue = new Set();
      if (item.span) for (var g = item.span[0] + 1; g < item.span[1]; g++) glue.add(g);
      var lines = wrap(item.words, fonts.lines, weights.lines, lineSize, regs.body.w, glue,
        reserve, item.span ? item.span[1] - 1 : null);
      lines.forEach(function (indices) {
        var span = lineHasMark(indices, item.span) ? item.span : null;
        var split = lineRuns(item.words, indices, fonts.lines, weights.lines, lineSize, span, span ? reserve : 0);
        body.push({ kind: "text", x: regs.body.x, y: cursor, height: lineSize * lh.lines,
          size: lineSize, family: fonts.lines, weight: weights.lines, runs: split.runs,
          mark_style: span ? item.style : null, line_index: item.index, number: number });
        cursor += lineSize * lh.lines;
      });
      if (item.note) notes.push({ number: number, text: item.note });
    });
    var noteY = regs.notes.y + 22, colGap = 18;
    var colW = (regs.notes.w - colGap) / 2;
    var noteRows = [], cursors = [noteY, noteY];
    notes.forEach(function (note) {
      var words = note.text.split(/\s+/).filter(Boolean);
      var lines = wrap(words, fonts.notes, weights.notes, noteSize, colW - 26, new Set());
      var col = cursors[0] <= cursors[1] ? 0 : 1;
      var y = cursors[col];
      lines.forEach(function (indices, li) {
        var split = lineRuns(words, indices, fonts.notes, weights.notes, noteSize, null, 0);
        noteRows.push({ x: regs.notes.x + col * (colW + colGap) + 26, y: y + li * noteSize * lh.notes,
          height: noteSize * lh.notes, size: noteSize, family: fonts.notes,
          weight: weights.notes, runs: split.runs, number: li === 0 ? note.number : null });
      });
      cursors[col] = y + lines.length * noteSize * lh.notes + 4;
    });
    return { body: body, notes: noteRows, body_height: cursor - regs.body.y,
      notes_height: Math.max(cursors[0], cursors[1]) - regs.notes.y };
  }

  function headerText(card) {
    var label = card.category_label || (card.category || "").replace(/-/g, " ").replace(/\b\w/g, function (c) { return c.toUpperCase(); });
    return label + (card.pill ? " · " + card.pill : "");
  }

  // ---------------------------------------------------------------- marks
  function runBounds(runs) {
    var marked = runs.filter(function (r) { return r.marked; });
    if (!marked.length) return null;
    var first = marked[0], last = marked[marked.length - 1];
    return [first.x, last.x + last.width];
  }

  function markPoints(styleName, x, width, baseline, lineHeight, style, card, lineIndex) {
    var def = style.marks.styles[styleName] || style.marks.styles.underline;
    var shape = def.shape, params = def.params || {};
    var wobble = style.wobble;
    var seed = markSeed(card.n, lineIndex, 3);
    var stroke = style.mark_stroke || params.stroke_width || 2.2;
    var out = [];
    if (shape === "cubic") {
      var pts = swashPoints(width, params.height_px || 8, params.points || 6,
        params.amplitude_px || 2.2, seed, wobble);
      var offset = baseline + (params.offset_px || 5);
      out.push({ type: "polyline", points: pts.map(function (p) { return [x + p[0], offset + p[1]]; }),
        stroke: stroke, color: style.theme.mark_colors[styleName] || "$category" });
    } else if (shape === "line") {
      var line = underlinePoints(width, params.amplitude_px || 0, seed, wobble);
      var loff = baseline + (params.offset_px || 4);
      out.push({ type: "polyline", points: line.map(function (p) { return [x + p[0], loff + p[1]]; }),
        stroke: stroke, color: style.theme.mark_colors[styleName] || "$category" });
    } else if (shape === "highlight") {
      var top = baseline - lineHeight + (params.top || 0.52) * lineHeight;
      var bottom = baseline - lineHeight + (params.bottom || 0.92) * lineHeight;
      out.push({ type: "polygon", points: highlightPolygon(x, top, bottom, width,
        params.inset_px || 2, params.amplitude_px || 1.4, params.points || 6, seed, wobble),
        color: style.theme.mark_colors[styleName] || "$tint" });
    }
    return out;
  }

  function badgeFor(right, baseline, cfg, number) {
    var d = cfg.diameter_px || 15, gap = cfg.gap_px || 2, lift = cfg.lift_px || 5;
    return { x: right + gap, cy: baseline - lift, d: d, font_size: cfg.font_size || 10, text: String(number) };
  }

  function addShapes(plan, style, card) {
    var marks = [], badges = [];
    var cfg = style.marks.badge.params || {};
    var baselineFor = function (row) {
      // Browser and Pillow both place the baseline at the top of the line box
      // plus the font's ascent. The fit plan's boxes are shared, so use the same
      // metric source the DOM uses: the ascent table measured by render_core.
      return row.y + ascentFraction(style, row.family, row.weight) * row.size;
    };
    if (plan.layout === "stacked") {
      (plan.body.marks || []).forEach(function (m) {
        var b = runBounds(m.runs); if (!b) return;
        marks = marks.concat(markPoints(style.mapMark(m.style), m.x + b[0], b[1] - b[0],
          baselineFor(m), m.height, style, card, m.line_index));
      });
      delete plan.body.marks;
    } else if (plan.layout === "notebook") {
      (plan.body.marks || []).forEach(function (m) {
        var b = runBounds(m.runs); if (!b) return;
        marks = marks.concat(markPoints(style.mapMark(m.style), m.x + b[0], b[1] - b[0],
          baselineFor(m), m.height, style, card, m.line_index));
        if (m.number) badges.push(badgeFor(m.x + b[1], baselineFor(m), cfg, m.number));
      });
      delete plan.body.marks;
    } else {
      plan.body.rows.forEach(function (row) {
        if (!row.mark_style) return;
        var b = runBounds(row.runs); if (!b) return;
        marks = marks.concat(markPoints(style.mapMark(row.mark_style), row.x + b[0], b[1] - b[0],
          baselineFor(row), row.height, style, card, row.line_index));
        if (row.number) badges.push(badgeFor(row.x + b[1], baselineFor(row), cfg, row.number));
      });
    }
    marks.forEach(function (m) { m.color = resolveColor(m.color, style, card); });
    plan.marks = marks;
    plan.badges = badges;
    return plan;
  }

  // The ascent the plan uses comes from the same font file in both renderers.
  // render_core.py measures it and the style bundle carries it as style.ascent,
  // so the shared boxes do not depend on a guess about browser metrics.
  function ascentFraction(style, family, weight) {
    var face = family;
    if (weight >= 600) {
      var bold = family + " Bold";
      if (style.ascent && style.ascent[bold] != null) face = bold;
    }
    var table = style.ascent || {};
    return table[face] != null ? table[face] : 0.92;
  }

  function resolveColor(token, style, card) {
    if (token === "$category") return style.accent;
    if (token === "$tint") return style.theme.tint;
    if (token.charAt(0) === "$") return style.theme[token.slice(1)] || style.theme.ink;
    return token;
  }

  function planCard(card, style) {
    var plan = style.layout_name === "notebook" ? planNotebook(card, style)
      : style.layout_name === "index" ? planIndex(card, style) : planStacked(card, style);
    return addShapes(plan, style, card);
  }

  // ---------------------------------------------------------------- DOM
  function el(tag, className, styles) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (styles) node.setAttribute("style", styles);
    return node;
  }

  /* Line height that puts the baseline exactly ``ascentPx`` below the top of
     the row, as Pillow does. An empty inline-block with height zero sits on
     the baseline, so probe it at line-height 0 and use the linear relation
     baseline = c + lineHeight / 2. */
  var lineHeightCache = {};

  function lineHeightFor(family, weight, size, ascentPx) {
    var key = family + "|" + weight + "|" + size + "|" + ascentPx;
    if (Object.prototype.hasOwnProperty.call(lineHeightCache, key)) return lineHeightCache[key];
    ensureMeasurer();
    var box = document.createElement("div");
    box.style.cssText = "position:absolute;left:-9999px;top:0;white-space:pre;line-height:0;" +
      "font-family:'" + family + "';font-weight:" + weight + ";" +
      "font-size:" + size + "px;" + variationCss(family, weight);
    var probe = document.createElement("span");
    probe.style.cssText = "display:inline-block;width:0;height:0;vertical-align:baseline;";
    box.appendChild(probe);
    measurer.appendChild(box);
    var c = probe.getBoundingClientRect().top - box.getBoundingClientRect().top;
    measurer.removeChild(box);
    var lh = Math.round(2 * (ascentPx - c) * 1000) / 1000;
    lineHeightCache[key] = lh;
    return lh;
  }

  function baselineStyle(style, family, weight, size, baselineAbs) {
    var ascentPx = ascentFraction(style, family, weight) * size;
    var lh = lineHeightFor(family, weight, size, ascentPx);
    return "height:" + lh + "px;line-height:" + lh + "px;top:" + (baselineAbs - ascentPx) +
      "px;font-family:'" + family + "';font-weight:" + weight + ";font-size:" + size +
      "px;white-space:pre;" + variationCss(family, weight);
  }

  function textStyle(row, style) {
    var ascentPx = ascentFraction(style, row.family, row.weight) * row.size;
    var lh = lineHeightFor(row.family, row.weight, row.size, ascentPx);
    return "position:absolute;left:" + row.x + "px;top:" + row.y + "px;" +
      "height:" + lh + "px;line-height:" + lh + "px;" +
      "font-family:'" + row.family + "';font-weight:" + row.weight + ";" +
      "font-size:" + row.size + "px;white-space:pre;" + variationCss(row.family, row.weight);
  }

  function addRow(root, row, color, style) {
    var wrapEl = el("div", "row", textStyle(row, style));
    row.runs.forEach(function (run) {
      var span = el("span", run.marked ? "run marked" : "run",
        "position:absolute;left:" + run.x + "px;top:0;white-space:pre;color:" + color + ";");
      span.textContent = run.text;
      wrapEl.appendChild(span);
    });
    root.appendChild(wrapEl);
  }

  function svgMark(mark, color, stroke) {
    var NS = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(NS, "svg");
    svg.setAttribute("class", "mark");
    svg.setAttribute("width", CARD_PX);
    svg.setAttribute("height", CARD_PX);
    svg.setAttribute("viewBox", "0 0 " + CARD_PX + " " + CARD_PX);
    var node;
    if (mark.type === "polyline") {
      node = document.createElementNS(NS, "polyline");
      node.setAttribute("points", mark.points.map(function (p) { return p[0] + "," + p[1]; }).join(" "));
      node.setAttribute("fill", "none");
      node.setAttribute("stroke", color);
      node.setAttribute("stroke-width", stroke || mark.stroke);
      node.setAttribute("stroke-linecap", "round");
      node.setAttribute("stroke-linejoin", "round");
    } else {
      node = document.createElementNS(NS, "polygon");
      node.setAttribute("points", mark.points.map(function (p) { return p[0] + "," + p[1]; }).join(" "));
      node.setAttribute("fill", color);
    }
    svg.appendChild(node);
    return svg;
  }

  function buildDom(plan, style, card) {
    var root = el("div", "card");
    root.dataset.layout = plan.layout;
    var vars = [
      ["--bg", style.theme.background], ["--ink", style.theme.ink],
      ["--muted", style.theme.muted], ["--accent", style.accent],
      ["--tint", style.theme.tint || style.theme.ink], ["--rule", style.theme.rule || style.theme.muted],
      ["--on-accent", style.theme.on_accent || "#ffffff"],
      ["--corner-radius", style.corner_radius + "px"],
      ["--mark-stroke", (style.mark_stroke || 2.2) + "px"],
      ["--mark-wobble", style.wobble],
      ["--font-title", "'" + style.fonts.title + "'"],
      ["--font-lines", "'" + style.fonts.lines + "'"],
      ["--font-notes", "'" + style.fonts.notes + "'"]
    ];
    vars.forEach(function (pair) { root.style.setProperty(pair[0], pair[1]); });

    var layer = el("div", "marks");
    plan.marks.forEach(function (mark) {
      layer.appendChild(svgMark(mark, mark.color, mark.stroke));
    });
    root.appendChild(layer);

    if (plan.layout === "stacked") {
      var wm = el("div", "watermark", "right:26px;color:var(--rule);" +
        baselineStyle(style, "Archivo Black", 400, 64, 74));
      wm.textContent = plan.labels.watermark;
      root.appendChild(wm);
    } else if (plan.layout === "notebook") {
      root.appendChild(el("div", "margin-rule",
        "left:" + plan.body.rule.x + "px;width:" + plan.body.rule.w + "px;background:var(--accent);opacity:.5;"));
      var num = el("div", "number", "right:28px;color:var(--accent);" +
        baselineStyle(style, "Fraunces", 600, 22, 24));
      num.textContent = plan.labels.number;
      root.appendChild(num);
    } else {
      root.appendChild(el("div", "band",
        "left:" + plan.band.x + "px;top:" + plan.band.y + "px;width:" + plan.band.w + "px;height:" + plan.band.h + "px;background:var(--accent);"));
    }

    var headerBaseline = plan.layout === "index" ? 28 : style.region("header").y + 9;
    var header = el("div", "header", "left:" + (plan.layout === "index" ? 28 : style.region("header").x) +
      "px;letter-spacing:1.6px;text-transform:uppercase;color:" +
      (plan.layout === "index" ? "var(--on-accent)" : "var(--muted)") + ";" +
      baselineStyle(style, "Atkinson Hyperlegible", 700, 11, headerBaseline));
    header.textContent = plan.labels.header;
    root.appendChild(header);
    if (plan.layout === "index") {
      var no = el("div", "header-number", "right:28px;letter-spacing:1.6px;color:var(--on-accent);opacity:.85;" +
        baselineStyle(style, "Atkinson Hyperlegible", 700, 11, 28));
      no.textContent = plan.labels.number;
      root.appendChild(no);
    }

    if (plan.title.highlight) {
      var h = plan.title.highlight;
      root.appendChild(el("div", "title-highlight", "left:" + h.x + "px;top:" + h.y + "px;width:" +
        h.w + "px;height:" + h.h + "px;background:var(--tint);"));
    }
    var titleAscent = ascentFraction(style, plan.title.family, plan.title.weight) * plan.title.size;
    var titleLine = lineHeightFor(plan.title.family, plan.title.weight, plan.title.size, titleAscent);
    plan.title.runs.forEach(function (run) {
      var node = el("div", "title-run", "position:absolute;left:" + (plan.title.x + run.x) + "px;top:" +
        (plan.title.y + (run.row || 0) * plan.title.line_height) + "px;height:" + titleLine +
        "px;line-height:" + titleLine + "px;font-family:'" + plan.title.family +
        "';font-weight:" + plan.title.weight + ";font-size:" + plan.title.size +
        "px;white-space:pre;color:" + plan.title.color + ";" + variationCss(plan.title.family, plan.title.weight));
      node.textContent = run.text;
      root.appendChild(node);
    });

    if (plan.layout === "stacked") {
      plan.body.rows.forEach(function (row) { addRow(root, row, "var(--ink)", style); });
    } else if (plan.layout === "notebook") {
      plan.body.lines.forEach(function (row) { addRow(root, row, "var(--ink)", style); });
      plan.body.notes.forEach(function (row) { addRow(root, row, "var(--ink)", style); });
    } else {
      plan.body.rows.forEach(function (row) { addRow(root, row, "var(--ink)", style); });
      var label = el("div", "try-this", "left:" + plan.notes.x +
        "px;letter-spacing:1.6px;text-transform:uppercase;color:var(--muted);" +
        baselineStyle(style, "Atkinson Hyperlegible", 700, 11, plan.notes.y + 11));
      label.textContent = plan.labels.try_this;
      root.appendChild(label);
      root.appendChild(el("div", "notes-rule", "left:" + plan.notes.x + "px;top:" + (plan.notes.y - 12) +
        "px;width:424px;height:1.5px;background:var(--rule);"));
      plan.notes.rows.forEach(function (row) { addRow(root, row, "var(--ink)", style); });
      plan.notes.rows.forEach(function (row) {
        if (row.number == null) return;
        var box = el("div", "note-number", "left:" + (row.x - 26) + "px;top:" +
          (row.y + row.height / 2 - 8.5) + "px;width:17px;height:17px;line-height:17px;text-align:center;background:var(--accent);color:var(--on-accent);font-family:'Atkinson Hyperlegible';font-weight:700;font-size:11px;");
        box.textContent = row.number;
        root.appendChild(box);
      });
    }

    plan.badges.forEach(function (badge) {
      var node = el("div", "badge", "left:" + badge.x + "px;top:" + (badge.cy - badge.d / 2) +
        "px;width:" + badge.d + "px;height:" + badge.d + "px;line-height:" + badge.d +
        "px;font-size:" + badge.font_size + "px;background:var(--accent);color:var(--on-accent);font-family:'Atkinson Hyperlegible';font-weight:700;");
      node.textContent = badge.text;
      root.appendChild(node);
    });
    return root;
  }

  // ---------------------------------------------------------------- public
  function prepareStyle(deckStyle, card) {
    var layout = deckStyle.layout, preset = deckStyle.preset, theme = deckStyle.theme, marks = deckStyle.marks;
    if (typeof layout === "string") layout = window.__assets.layout(layout);
    if (typeof preset === "string") preset = window.__assets.preset(preset);
    if (typeof theme === "string") theme = window.__assets.theme(theme);
    var layoutName = deckStyle.layout_name || layout.name || deckStyle.layout;
    if (!preset.fonts[layoutName]) throw new Error("preset has no fonts for " + layoutName);
    // The style bundle carries the preset tokens already merged with any deck
    // overrides. Fall back to the preset's own tokens when it does not.
    var tokenWeights = {}, tk;
    var presetTokens = preset.tokens || {};
    for (tk in presetTokens) tokenWeights[tk] = presetTokens[tk];
    var deckTokens = (deckStyle.tokens && typeof deckStyle.tokens === "object") ? deckStyle.tokens : {};
    for (tk in deckTokens) tokenWeights[tk] = deckTokens[tk];
    // Weights are flat preset tokens: title_weight, lines_weight, notes_weight.
    var weights = {
      title: tokenWeights.title_weight || 400,
      lines: tokenWeights.lines_weight || 400,
      notes: tokenWeights.notes_weight || 400
    };
    var palette = theme.category_palette || {};
    var accent = deckStyle.accent || palette[card.category_color] ||
      palette[categoryColour(card.category || "")] || theme.ink;
    var style = {
      layout_name: layoutName,
      layout: layout,
      preset: preset,
      theme: theme,
      marks: marks || (window.__assets && window.__assets.marks()) || deckStyle.marks,
      fonts: preset.fonts[layoutName],
      weights: weights,
      tokens: tokenWeights,
      ascent: deckStyle.ascent || {},
      spacing: tokenWeights.spacing || 1,
      mark_stroke: tokenWeights.mark_stroke || 2.2,
      // Mark wobble is a token (SPEC section 7), so a deck token wins over
      // the preset's default; 0 gives clean geometric marks.
      wobble: tokenWeights.mark_wobble != null ? Number(tokenWeights.mark_wobble)
        : (preset.mark_wobble == null ? 1 : preset.mark_wobble),
      mark_wobble: tokenWeights.mark_wobble != null ? Number(tokenWeights.mark_wobble)
        : preset.mark_wobble,
      corner_radius: preset.corner_radius,
      accent: accent,
      mapMark: function (name) {
        var mapped = (preset.mark_styles || {})[name];
        return mapped || name;
      },
      region: function (name) { return region(layout, name); }
    };
    return style;
  }

  var CATEGORY_ORDER = ["orange", "teal", "blue", "green", "purple", "red", "pink", "amber"];
  function categoryColour(category) {
    var total = 0;
    for (var i = 0; i < category.length; i++) total += category.charCodeAt(i);
    return CATEGORY_ORDER[total % CATEGORY_ORDER.length];
  }

  function ensureMeasurer() {
    if (!measurer) {
      measurer = el("div", "measurer");
      measurer.setAttribute("aria-hidden", "true");
      document.body.appendChild(measurer);
    }
  }

  function renderInto(card, deckStyle, host) {
    ensureMeasurer();
    var style = prepareStyle(deckStyle, card);
    var plan = planCard(card, style);
    host.innerHTML = "";
    host.appendChild(buildDom(plan, style, card));
    window.__report = Object.assign({ n: card.n, layout: plan.layout }, plan.report, {
      lines: lineTexts(plan)
    });
    return plan;
  }

  function render(card, deckStyle, format) {
    return renderInto(card, deckStyle, document.getElementById("card"));
  }

  function lineTexts(plan) {
    var rows = plan.body.rows || plan.body.lines || [];
    return rows.filter(function (r) { return r.kind === "text"; }).map(function (r) {
      return r.runs.map(function (run) { return run.text; }).join("");
    });
  }

  global.Tuckcard = { render: render, renderInto: renderInto, loadFonts: loadFonts,
    plan: function (card, deckStyle) { return planCard(card, prepareStyle(deckStyle, card)); },
    mulberry32: mulberry32, measure: measure };
})(window);
