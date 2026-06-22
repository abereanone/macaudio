// Scripture reference parsing (TypeScript port of tools/sermons/scripture.py).
// Used to extract references from manually-pasted transcripts so they feed the
// scripture index the same way the Python backfill does. Regex-based.

const BOOKS: Record<string, string[]> = {
  Genesis: ["gen", "ge", "gn"], Exodus: ["exod", "exo", "ex"], Leviticus: ["lev", "lv"],
  Numbers: ["num", "nm", "nu"], Deuteronomy: ["deut", "dt"], Joshua: ["josh", "jos"],
  Judges: ["judg", "jdg"], Ruth: ["rth", "ru"],
  "1 Samuel": ["1 sam", "1sam", "1 sm", "first samuel", "i samuel"],
  "2 Samuel": ["2 sam", "2sam", "2 sm", "second samuel", "ii samuel"],
  "1 Kings": ["1 kgs", "1kgs", "1 ki", "first kings", "i kings"],
  "2 Kings": ["2 kgs", "2kgs", "2 ki", "second kings", "ii kings"],
  "1 Chronicles": ["1 chron", "1 chr", "1chr", "first chronicles", "i chronicles"],
  "2 Chronicles": ["2 chron", "2 chr", "2chr", "second chronicles", "ii chronicles"],
  Ezra: ["ezr"], Nehemiah: ["neh"], Esther: ["esth", "est"], Job: ["jb"],
  Psalms: ["psalm", "pss", "ps", "psa", "psalms"], Proverbs: ["prov", "prv", "pr"],
  Ecclesiastes: ["eccles", "eccl", "ecc", "qoh"],
  "Song of Solomon": ["song", "song of songs", "sos", "canticles"],
  Isaiah: ["isa", "is"], Jeremiah: ["jer", "jr"], Lamentations: ["lam"],
  Ezekiel: ["ezek", "eze"], Daniel: ["dan", "dn"], Hosea: ["hos"], Joel: ["joe", "jl"],
  Amos: ["am"], Obadiah: ["obad", "ob"], Jonah: ["jon"], Micah: ["mic", "mc"],
  Nahum: ["nah", "na"], Habakkuk: ["hab", "hb"], Zephaniah: ["zeph", "zep"],
  Haggai: ["hag", "hg"], Zechariah: ["zech", "zec"], Malachi: ["mal"],
  Matthew: ["matt", "mt"], Mark: ["mrk", "mk", "mr"], Luke: ["luk", "lk"],
  John: ["john", "jhn", "jn", "joh"], Acts: ["act"], Romans: ["rom", "rm"],
  "1 Corinthians": ["1 cor", "1cor", "first corinthians", "i corinthians"],
  "2 Corinthians": ["2 cor", "2cor", "second corinthians", "ii corinthians"],
  Galatians: ["gal"], Ephesians: ["eph"], Philippians: ["phil", "php"], Colossians: ["col"],
  "1 Thessalonians": ["1 thess", "1 thes", "1thess", "first thessalonians", "i thessalonians"],
  "2 Thessalonians": ["2 thess", "2 thes", "2thess", "second thessalonians", "ii thessalonians"],
  "1 Timothy": ["1 tim", "1tim", "first timothy", "i timothy"],
  "2 Timothy": ["2 tim", "2tim", "second timothy", "ii timothy"],
  Titus: ["tit"], Philemon: ["philem", "phlm"], Hebrews: ["heb"], James: ["jas", "jm"],
  "1 Peter": ["1 pet", "1pet", "1 pt", "first peter", "i peter"],
  "2 Peter": ["2 pet", "2pet", "2 pt", "second peter", "ii peter"],
  "1 John": ["1 jn", "1jn", "1 jhn", "first john", "i john"],
  "2 John": ["2 jn", "2jn", "2 jhn", "second john", "ii john"],
  "3 John": ["3 jn", "3jn", "3 jhn", "third john", "iii john"],
  Jude: ["jud"], Revelation: ["rev", "rv", "apocalypse", "revelations"],
};

const ALIAS = new Map<string, string>();
for (const [canon, aliases] of Object.entries(BOOKS)) {
  ALIAS.set(canon.toLowerCase(), canon);
  for (const a of aliases) ALIAS.set(a, canon);
}
const BOOK_ALTS = [...ALIAS.keys()].sort((a, b) => b.length - a.length).map((b) => b.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
const REF_RE = new RegExp(
  `\\b(${BOOK_ALTS.join("|")})\\.?\\s*(\\d{1,3})(?:\\s*[:.]\\s*(\\d{1,3})(?:\\s*[-–]\\s*(\\d{1,3}))?)?`,
  "gi"
);

export interface Ref { book: string; chapter: number; verse_start: number | null; verse_end: number | null; ref_text: string; }

export function parseRefs(text: string): Ref[] {
  const out: Ref[] = [];
  const seen = new Set<string>();
  for (const m of (text || "").matchAll(REF_RE)) {
    const canon = ALIAS.get(m[1].toLowerCase().replace(/\.$/, ""));
    if (!canon) continue;
    const chapter = parseInt(m[2], 10);
    const vs = m[3] ? parseInt(m[3], 10) : null;
    const ve = m[4] ? parseInt(m[4], 10) : null;
    const key = `${canon}|${chapter}|${vs}|${ve}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ book: canon, chapter, verse_start: vs, verse_end: ve, ref_text: m[0].trim() });
  }
  return out;
}
