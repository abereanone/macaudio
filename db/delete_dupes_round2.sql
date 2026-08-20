-- Round 2 dedupe: 25 duplicate copies (podcast re-releases, raw-filename imports,
-- and a wrong-year import batch where 2020-xx-xx shadowed the real 2021 sermon).
-- Each verified transcript-identical with duration matching to the second; every
-- survivor confirmed to still have its audio in R2 first.
DELETE FROM items WHERE id IN (131,132,133,134,135,136,137,145,177,178,179,180,182,183,184,185,186,187,188,189,190,191,192,195,200);
