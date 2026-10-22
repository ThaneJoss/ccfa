/* Runs in Zotero's isolated plugin scope and in Node's test runner. */
"use strict";

var CCFAMatcher = (() => {
  const NON_MAIN = /\b(?:workshops?|cvprw|iccvw|companion|adjunct|findings|demos?|demonstrations?|tutorials?|posters?|doctoral|short papers?|extended abstracts?|technical briefs?|student research)\b/i;
  const WRAPPER = new Set([
    "proceedings", "proceeding", "of", "the", "on", "for", "and", "in",
    "acm", "ieee", "cvf", "ifip", "usenix", "sigplan", "sigact", "sigops", "siam",
    "annual", "international", "joint", "conference", "symposium", "meeting"
  ]);

  function normalize(value) {
    return String(value || "").normalize("NFKC")
      .replace(/&amp;/gi, " and ").replace(/&/g, " and ")
      .replace(/<[^>]*>/g, " ").replace(/[{}]/g, "")
      .normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
      .toLowerCase().replace(/[^a-z0-9]+/g, " ").trim().replace(/\s+/g, " ");
  }

  function signature(value) {
    return normalize(value).split(" ")
      .filter(w => !WRAPPER.has(w) && !/^(?:19|20)\d{2}$/.test(w) && !/^\d+(?:st|nd|rd|th)$/.test(w))
      .join(" ");
  }

  function add(map, key, venue) {
    if (!key) return;
    const previous = map.get(key);
    // Conflicting spellings are deliberately ambiguous, never first-match wins.
    map.set(key, previous && previous !== venue ? null : (map.has(key) && previous === null ? null : venue));
  }

  function create(catalog) {
    const exact = new Map();
    const conferences = new Map();
    for (const venue of catalog.venues) {
      const aliases = [...new Set([venue.name, venue.abbr, ...venue.aliases])];
      for (const alias of aliases) add(exact, normalize(alias), venue);
      if (venue.type !== "conference") continue;
      for (const alias of aliases) {
        const key = signature(alias);
        // One-word full titles such as Multimedia are too broad by themselves.
        if (key.split(" ").length >= 2 || venue.acronyms.some(a => signature(a) === key)) {
          add(conferences, key, venue);
        }
        for (const acronym of venue.acronyms) {
          add(conferences, signature(alias + " " + acronym), venue);
          add(conferences, signature(acronym + " " + alias), venue);
        }
      }
    }

    function match(value) {
      const normalized = normalize(value);
      if (!normalized || NON_MAIN.test(normalized)) return "";
      const withoutYear = normalized.split(" ")
        .filter(w => !/^(?:19|20)\d{2}$/.test(w) && !/^\d+(?:st|nd|rd|th)$/.test(w)).join(" ");
      // Do not turn the journal "Machine Learning" into the ICML conference,
      // or "Real-Time Systems" into RTSS by stripping all conference words.
      const hasConferenceContext = /\b(?:conference|symposium|meeting|proceedings)\b/.test(normalized);
      const venue = exact.get(normalized) || exact.get(withoutYear)
        || (hasConferenceContext ? conferences.get(signature(value)) : null);
      return venue ? venue.abbr : "";
    }

    function field(item, name, mapBase = false) {
      try { return String(item.getField(name, false, mapBase) || "").trim(); }
      catch (_) { return ""; } // Not every item type has every field.
    }

    function forItem(item) {
      if (!item || !item.isRegularItem || !item.isRegularItem() || item.deleted) return "";
      const publication = field(item, "publicationTitle", true);
      const proceedings = field(item, "proceedingsTitle");
      const book = field(item, "bookTitle");
      const conference = field(item, "conferenceName");
      const sources = [...new Set([publication, proceedings, book, conference].filter(Boolean))];
      // An explicit workshop/findings container must not be overridden by a parent conference field.
      if (sources.some(s => NON_MAIN.test(normalize(s)))) return "";
      if (!sources.length) return match(field(item, "journalAbbreviation"));
      const values = [...new Set(sources.map(match).filter(Boolean))];
      // Conflicting venue fields require a metadata correction, not a guess.
      return values.length === 1 ? values[0] : "";
    }

    return Object.freeze({ match, forItem });
  }
  return Object.freeze({ create, normalize });
})();

if (typeof module !== "undefined") module.exports = CCFAMatcher;
