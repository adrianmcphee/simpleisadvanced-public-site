/* RSVP Reader — Illusions of Work */
(function () {
  "use strict";

  // --- State ---
  var meta = null;
  var chapters = [];
  var chapterOffsets = [];  // global word index where each chapter starts
  var chapterWords = {};    // cache: chapterId -> word array
  var loadingChapters = {}; // in-flight fetches
  var totalWords = 0;
  var pos = 0;
  var playing = false;
  var titleCard = false;  // true when showing initial title screen
  var timer = null;
  var wpm = 350;
  var chunkSize = 1;
  var orpEnabled = true;
  var theme = "light";
  var fontSize = "medium";

  // --- DOM refs ---
  var wordPre, wordOrp, wordPost, chapterTitle, chapterSubtitle,
      progressFill, playBtn, wpmDisplay, tocOverlay,
      tocList, display, iconPlay, iconPause, timeCurrent, timeTotal;

  function cacheDom() {
    wordPre = document.getElementById("word-pre");
    wordOrp = document.getElementById("word-orp");
    wordPost = document.getElementById("word-post");
    chapterTitle = document.getElementById("chapter-title");
    chapterSubtitle = document.getElementById("chapter-subtitle");
    progressFill = document.getElementById("progress-fill");
    playBtn = document.getElementById("play-btn");
    wpmDisplay = document.getElementById("wpm-display");
    tocOverlay = document.getElementById("toc-overlay");
    tocList = document.getElementById("toc-list");
    display = document.getElementById("display");
    iconPlay = document.getElementById("icon-play");
    iconPause = document.getElementById("icon-pause");
    timeCurrent = document.getElementById("time-current");
    timeTotal = document.getElementById("time-total");
  }

  // --- Analytics ---
  var lastAnalyticsChapter = -1;
  var progressTimer = null;
  var sessionStart = Date.now();

  function track(event, props) {
    if (typeof plausible === 'function') {
      plausible(event, props ? { props: props } : undefined);
    }
  }

  function chapterLabel(idx) {
    var ch = chapters[idx];
    if (!ch) return '';
    return ch.chapterNum ? 'Ch ' + ch.chapterNum : ch.title;
  }

  function trackChapterStart(chIdx) {
    lastAnalyticsChapter = chIdx;
    track('Chapter Start', {
      chapter: chapterLabel(chIdx),
      title: chapters[chIdx].title
    });
  }

  function trackChapterComplete(chIdx) {
    track('Chapter Complete', {
      chapter: chapterLabel(chIdx),
      title: chapters[chIdx].title
    });
  }

  function trackProgress() {
    var ch = chapterForPos(pos);
    track('Progress', {
      chapter: chapterLabel(ch),
      book_pct: String(Math.round((pos / totalWords) * 100))
    });
  }

  function startProgressTimer() {
    if (progressTimer) return;
    progressTimer = setInterval(trackProgress, 60000);
  }

  function stopProgressTimer() {
    if (progressTimer) {
      clearInterval(progressTimer);
      progressTimer = null;
    }
  }

  // --- Pause durations (ms added to base interval) ---
  var PAUSE = {
    comma: 150,
    sentence: 350,
    paragraph: 700,
    heading: 900,
    separator: 1200
  };

  // --- Chapter loading ---
  function buildOffsets() {
    chapterOffsets = [];
    var offset = 0;
    for (var i = 0; i < chapters.length; i++) {
      chapterOffsets.push(offset);
      offset += chapters[i].wordCount;
    }
  }

  function chapterForPos(p) {
    for (var i = chapters.length - 1; i >= 0; i--) {
      if (p >= chapterOffsets[i]) return i;
    }
    return 0;
  }

  function localPos(p) {
    var ch = chapterForPos(p);
    return { ch: ch, idx: p - chapterOffsets[ch] };
  }

  function getWord(p) {
    var loc = localPos(p);
    var words = chapterWords[loc.ch];
    if (!words) return null;
    return words[loc.idx] || null;
  }

  function isChapterLoaded(chId) {
    return chapterWords[chId] !== undefined;
  }

  function loadChapter(chId) {
    if (isChapterLoaded(chId) || loadingChapters[chId]) {
      return loadingChapters[chId] || Promise.resolve();
    }
    var file = "data/ch" + String(chId).padStart(2, "0") + ".json";
    var p = fetch("./" + file)
      .then(function (r) { return r.json(); })
      .then(function (words) {
        chapterWords[chId] = words;
        delete loadingChapters[chId];
      })
      .catch(function () {
        delete loadingChapters[chId];
      });
    loadingChapters[chId] = p;
    return p;
  }

  function ensureChaptersAround(p) {
    var ch = chapterForPos(p);
    var promises = [];
    // Load current, previous, and next chapter
    if (ch > 0) promises.push(loadChapter(ch - 1));
    promises.push(loadChapter(ch));
    if (ch < chapters.length - 1) promises.push(loadChapter(ch + 1));
    return Promise.all(promises);
  }

  // --- Load ---
  async function init() {
    cacheDom();

    try {
      var resp = await fetch("./data/meta.json");
      meta = await resp.json();
      chapters = meta.chapters;
      totalWords = meta.totalWords;
    } catch (e) {
      chapterTitle.textContent = "Failed to load book data";
      return;
    }

    buildOffsets();
    loadSettings();
    applyURLParams();

    if (meta.version) {
      var vl = document.getElementById("version-label");
      if (vl) vl.textContent = "v" + meta.version;
    }

    // First visit: show title card instead of Author's Note
    var hasURL = window.location.search.indexOf("ch=") >= 0 || window.location.search.indexOf("w=") >= 0 || window.location.hash.length > 1;
    if (pos === 0 && !hasURL) {
      titleCard = true;
      showTitleCard();
    } else {
      await ensureChaptersAround(pos);
      showWord();
    }

    buildTOC();
    updateTimeDisplay();
    setupEvents();
  }

  // --- ORP (Optimal Recognition Point) ---
  function orpIndex(word) {
    var len = word.length;
    if (len <= 1) return 0;
    if (len <= 3) return 0;
    if (len <= 5) return 1;
    if (len <= 9) return 2;
    if (len <= 13) return 3;
    return 4;
  }

  // --- Title card ---
  function showTitleCard() {
    wordPre.textContent = "";
    wordOrp.textContent = "";
    wordPost.textContent = meta.title;
    chapterTitle.textContent = meta.subtitle || "";
    chapterSubtitle.textContent = "by " + meta.author;
    updateProgress();
  }

  // --- Display ---
  function showWord() {
    if (!totalWords) return;
    if (pos >= totalWords) pos = totalWords - 1;
    if (pos < 0) pos = 0;

    var w = getWord(pos);
    if (!w) {
      var ch = chapterForPos(pos);
      if (isChapterLoaded(ch)) {
        // Chapter loaded but word missing — position is stale, reset to chapter start
        pos = chapterOffsets[ch];
        w = getWord(pos);
        if (!w && pos > 0) { pos = 0; w = getWord(pos); }
        if (!w) return; // give up
      } else {
        // Chapter not loaded yet — show loading state
        wordPre.textContent = "";
        wordOrp.textContent = "";
        wordPost.textContent = "…";
        ensureChaptersAround(pos).then(function () { showWord(); });
        return;
      }
    }

    var display_words = [];
    for (var i = 0; i < chunkSize; i++) {
      var wd = getWord(pos + i);
      if (wd) display_words.push(wd.w);
    }
    var text = display_words.join(" ");

    if (orpEnabled && chunkSize === 1) {
      var idx = orpIndex(text);
      wordPre.textContent = text.substring(0, idx);
      wordOrp.textContent = text[idx] || "";
      wordPost.textContent = text.substring(idx + 1);
    } else {
      wordPre.textContent = "";
      wordOrp.textContent = "";
      wordPost.textContent = text;
    }

    updateProgress();
    updateChapterTitle();
    updateTimeDisplay();
    savePosition();

    // Preload next chapter if we're getting close
    var ch = chapterForPos(pos);
    if (ch < chapters.length - 1) {
      var chEnd = chapterOffsets[ch] + chapters[ch].wordCount;
      if (pos > chEnd - 100) loadChapter(ch + 1);
    }
  }

  function updateProgress() {
    var pct = totalWords ? ((pos / totalWords) * 100) : 0;
    progressFill.style.width = pct + "%";
  }

  function currentChapter() {
    var idx = chapterForPos(pos);
    return chapters[idx];
  }

  function updateChapterTitle() {
    var ch = currentChapter();
    if (ch) {
      chapterTitle.textContent = ch.chapterNum ? "Chapter " + ch.chapterNum + ": " + ch.title : ch.title;
      chapterSubtitle.textContent = ch.part || "";
    }
  }

  function formatTime(minutes) {
    var m = Math.floor(minutes);
    var s = Math.round((minutes - m) * 60);
    if (s === 60) { m++; s = 0; }
    return m + ":" + (s < 10 ? "0" : "") + s;
  }

  function updateTimeDisplay() {
    if (!totalWords || !timeCurrent) return;
    var currentMin = pos / wpm;
    var totalMin = totalWords / wpm;
    timeCurrent.textContent = formatTime(currentMin);
    timeTotal.textContent = formatTime(totalMin);
  }

  // --- Hide controls briefly after play ---
  var hideTimer = null;
  function hideControlsBriefly() {
    var footer = document.querySelector("footer");
    if (!footer) return;
    if (hideTimer) clearTimeout(hideTimer);
    footer.classList.add("controls-hidden");
    hideTimer = setTimeout(function () {
      footer.classList.remove("controls-hidden");
      hideTimer = null;
    }, 2000);
  }

  // --- Playback ---
  function baseInterval() {
    return 60000 / wpm;
  }

  function scheduleNext() {
    if (!playing) return;
    if (pos >= totalWords - 1) {
      pause();
      return;
    }

    var delay = baseInterval() * chunkSize;
    var lastPos = Math.min(pos + chunkSize - 1, totalWords - 1);
    var lastWord = getWord(lastPos);
    if (lastWord) {
      var pauseType = lastWord.p;
      if (pauseType && PAUSE[pauseType]) {
        delay += PAUSE[pauseType];
      }
    }

    timer = setTimeout(function () {
      var prevCh = chapterForPos(pos);
      pos += chunkSize;
      if (pos >= totalWords) pos = totalWords - 1;
      var newCh = chapterForPos(pos);

      // Detect chapter boundary crossing during playback
      if (newCh !== prevCh) {
        trackChapterComplete(prevCh);
        trackChapterStart(newCh);
      }

      // Check if word is available
      var w = getWord(pos);
      if (!w) {
        // Need to load chapter, pause briefly
        ensureChaptersAround(pos).then(function () {
          showWord();
          scheduleNext();
        });
        return;
      }

      showWord();
      scheduleNext();
    }, delay);
  }

  function play() {
    if (!totalWords) return;
    // From title card, jump to startChapter (skip Author's Note)
    if (titleCard) {
      titleCard = false;
      var sc = (meta.startChapter || 0);
      if (sc > 0 && sc < chapters.length) {
        pos = chapterOffsets[sc];
      }
      ensureChaptersAround(pos).then(function () {
        showWord();
        trackChapterStart(chapterForPos(pos));
        playing = true;
        iconPlay.classList.add("hidden");
        iconPause.classList.remove("hidden");
        hideControlsBriefly();
        startProgressTimer();
        scheduleNext();
      });
      return;
    }
    if (lastAnalyticsChapter !== chapterForPos(pos)) {
      trackChapterStart(chapterForPos(pos));
    }
    playing = true;
    iconPlay.classList.add("hidden");
    iconPause.classList.remove("hidden");
    hideControlsBriefly();
    startProgressTimer();
    scheduleNext();
  }

  function pause() {
    playing = false;
    iconPlay.classList.remove("hidden");
    iconPause.classList.add("hidden");
    stopProgressTimer();
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
  }

  function togglePlay() {
    if (titleCard) { play(); return; }
    if (playing) pause();
    else play();
  }

  // --- Navigation ---
  function skipWords(n) {
    pause();
    pos = Math.max(0, Math.min(totalWords - 1, pos + n));
    ensureChaptersAround(pos).then(function () { showWord(); });
  }

  function goToChapter(idx) {
    pause();
    if (idx >= 0 && idx < chapters.length) {
      pos = chapterOffsets[idx];
      trackChapterStart(idx);
      ensureChaptersAround(pos).then(function () { showWord(); });
    }
    closeTOC();
  }

  function prevChapter() {
    var ch = currentChapter();
    if (!ch) return;
    if (pos > chapterOffsets[ch.id] + 10) {
      goToChapter(ch.id);
    } else {
      goToChapter(Math.max(0, ch.id - 1));
    }
  }

  function nextChapter() {
    var ch = currentChapter();
    if (!ch) return;
    goToChapter(Math.min(chapters.length - 1, ch.id + 1));
  }

  function replayChapter() {
    var ch = currentChapter();
    if (ch) goToChapter(ch.id);
  }

  // --- WPM ---
  function adjustWPM(delta) {
    wpm = Math.max(50, Math.min(1200, wpm + delta));
    wpmDisplay.textContent = wpm + " wpm";
    updateTimeDisplay();
    saveSettings();
    track('Speed Change', { wpm: String(wpm) });
  }

  // --- TOC ---
  function buildTOC() {
    tocList.innerHTML = "";
    var currentPart = null;
    for (var i = 0; i < chapters.length; i++) {
      var ch = chapters[i];
      if (ch.part && ch.part !== currentPart) {
        currentPart = ch.part;
        var partLi = document.createElement("li");
        partLi.className = "toc-part-header";
        partLi.textContent = ch.part;
        tocList.appendChild(partLi);
      }
      var li = document.createElement("li");
      var label = ch.chapterNum ? "Chapter " + ch.chapterNum + ": " + ch.title : ch.title;
      li.appendChild(document.createTextNode(label));
      li.addEventListener("click", (function (id) {
        return function () { goToChapter(id); };
      })(ch.id));
      tocList.appendChild(li);
    }
  }

  function openTOC() { tocOverlay.classList.remove("hidden"); }
  function closeTOC() { tocOverlay.classList.add("hidden"); }

  // --- URL deep linking ---
  function slugify(title) {
    return title.toLowerCase()
      .replace(/[^\w\s-]/g, "")
      .replace(/[\s_]+/g, "-")
      .replace(/-+/g, "-")
      .replace(/^-|-$/g, "");
  }

  function applyURLParams() {
    var params = new URLSearchParams(window.location.search);
    if (params.has("ch")) {
      var chNum = parseInt(params.get("ch"), 10);
      for (var i = 0; i < chapters.length; i++) {
        if (chapters[i].chapterNum === chNum) {
          pos = chapterOffsets[i];
          break;
        }
      }
    }
    if (params.has("w")) {
      var wIdx = parseInt(params.get("w"), 10);
      if (wIdx >= 0 && wIdx < totalWords) {
        pos = wIdx;
      }
    }
    // Handle hash fragment deep links (e.g. #the-transition-and-its-failure-modes)
    var hash = window.location.hash.replace(/^#/, "");
    if (hash && !params.has("ch") && !params.has("w")) {
      for (var i = 0; i < chapters.length; i++) {
        if (slugify(chapters[i].title) === hash) {
          pos = chapterOffsets[i];
          break;
        }
      }
    }
  }

  function buildShareURL() {
    var ch = currentChapter();
    var url = new URL(window.location.href);
    url.search = "";
    url.hash = "";
    if (ch) {
      url.hash = slugify(ch.title);
      if (pos > chapterOffsets[ch.id] + 5) {
        url.searchParams.set("w", pos);
      }
    }
    return url.toString();
  }

  function showToast(msg) {
    var toast = document.getElementById("toast");
    toast.textContent = msg;
    toast.classList.remove("hidden");
    setTimeout(function () { toast.classList.add("hidden"); }, 2000);
  }

  function shareLink() {
    var url = buildShareURL();
    if (navigator.clipboard) {
      navigator.clipboard.writeText(url);
    }
    track('Share', { chapter: chapterLabel(chapterForPos(pos)) });
    showToast("Link copied");
  }

  function comingSoon(e) {
    e.preventDefault();
    track('Buy Click', { chapter: chapterLabel(chapterForPos(pos)) });
    showToast("Available soon");
  }

  // --- Progress bar click ---
  function onProgressClick(e) {
    var bar = document.getElementById("progress-bar");
    var rect = bar.getBoundingClientRect();
    var pct = (e.clientX - rect.left) / rect.width;
    pause();
    pos = Math.floor(pct * totalWords);
    ensureChaptersAround(pos).then(function () { showWord(); });
  }

  // --- Settings persistence ---
  function saveSettings() {
    try {
      localStorage.setItem("rsvp-settings", JSON.stringify({
        wpm: wpm,
        chunkSize: chunkSize,
        orpEnabled: orpEnabled,
        theme: theme,
        fontSize: fontSize
      }));
    } catch (e) { /* ignore */ }
  }

  function savePosition() {
    try {
      localStorage.setItem("rsvp-position", String(pos));
      localStorage.setItem("rsvp-totalWords", String(totalWords));
    } catch (e) { /* ignore */ }
  }

  function loadSettings() {
    try {
      var s = JSON.parse(localStorage.getItem("rsvp-settings"));
      if (s) {
        wpm = s.wpm || 350;
        chunkSize = s.chunkSize || 1;
        orpEnabled = s.orpEnabled !== false;
        theme = s.theme || "light";
        fontSize = s.fontSize || "medium";
      }
    } catch (e) { /* ignore */ }

    try {
      localStorage.removeItem("rsvp-version"); // clean up legacy key
      var savedTotal = localStorage.getItem("rsvp-totalWords");
      if (savedTotal && parseInt(savedTotal, 10) === totalWords) {
        var p = localStorage.getItem("rsvp-position");
        if (p) pos = Math.min(parseInt(p, 10) || 0, totalWords - 1);
      } else {
        // Word count changed — discard stale position
        localStorage.removeItem("rsvp-position");
      }
    } catch (e) { /* ignore */ }

    applyTheme();
    applyFontSize();
    wpmDisplay.textContent = wpm + " wpm";
  }

  function applyTheme() {
    document.documentElement.setAttribute("data-theme", theme);
  }

  function applyFontSize() {
    document.documentElement.setAttribute("data-fontsize", fontSize);
  }

  // --- Events ---
  function setupEvents() {
    playBtn.addEventListener("click", togglePlay);
    document.getElementById("back-btn").addEventListener("click", function () { skipWords(-10); });
    document.getElementById("fwd-btn").addEventListener("click", function () { skipWords(10); });
    document.getElementById("prev-btn").addEventListener("click", prevChapter);
    document.getElementById("next-btn").addEventListener("click", nextChapter);
    document.getElementById("wpm-down").addEventListener("click", function () { adjustWPM(-25); });
    document.getElementById("wpm-up").addEventListener("click", function () { adjustWPM(25); });
    document.getElementById("toc-btn").addEventListener("click", openTOC);
    document.getElementById("replay-btn").addEventListener("click", replayChapter);
    document.getElementById("share-btn-footer").addEventListener("click", shareLink);
    document.getElementById("buy-link").addEventListener("click", comingSoon);
    document.getElementById("buy-link-mobile").addEventListener("click", comingSoon);
    document.getElementById("buy-link-toc").addEventListener("click", comingSoon);
    document.getElementById("cover-thumb").addEventListener("click", comingSoon);
    document.getElementById("contact-link").addEventListener("click", function () {
      track('Contact Click', { chapter: chapterLabel(chapterForPos(pos)) });
    });
    document.getElementById("contact-link-mobile").addEventListener("click", function () {
      track('Contact Click', { chapter: chapterLabel(chapterForPos(pos)) });
    });
    var brandClickTimer = null;
    document.getElementById("sia-brand").addEventListener("click", function () {
      if (brandClickTimer) {
        clearTimeout(brandClickTimer);
        brandClickTimer = null;
        if (meta && meta.version) showToast("v" + meta.version);
      } else {
        brandClickTimer = setTimeout(function () {
          brandClickTimer = null;
          window.location.href = "/";
        }, 300);
      }
    });

    document.getElementById("progress-bar").addEventListener("click", onProgressClick);

    tocOverlay.querySelector(".close-btn").addEventListener("click", closeTOC);
    tocOverlay.addEventListener("click", function (e) { if (e.target === tocOverlay) closeTOC(); });

    document.addEventListener("keydown", function (e) {
      if (!tocOverlay.classList.contains("hidden")) {
        if (e.key === "Escape") { closeTOC(); }
        return;
      }
      switch (e.key) {
        case " ": e.preventDefault(); togglePlay(); break;
        case "ArrowLeft": skipWords(-10); break;
        case "ArrowRight": skipWords(10); break;
        case "ArrowUp": case "+": case "=": adjustWPM(25); break;
        case "ArrowDown": case "-": adjustWPM(-25); break;
        case "[": prevChapter(); break;
        case "]": nextChapter(); break;
      }
    });

    display.addEventListener("click", function (e) {
      var rect = display.getBoundingClientRect();
      var x = (e.clientX - rect.left) / rect.width;
      if (x < 0.33) { skipWords(-10); }
      else if (x > 0.66) { skipWords(10); }
      else { togglePlay(); }
    });

    // Track session end when user leaves or switches tab
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "hidden") {
        stopProgressTimer();
        var ch = chapterForPos(pos);
        var mins = Math.round((Date.now() - sessionStart) / 60000);
        track('Session End', {
          chapter: chapterLabel(ch),
          book_pct: String(Math.round((pos / totalWords) * 100)),
          reading_mins: String(mins)
        });
      }
    });
  }

  // --- Go ---
  init();
})();
