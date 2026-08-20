-- "Hunger and Thirst" (#233) is the podcast copy of "Blessed Are Those Who
-- Hunger" (#72) -- identical opening, 3/6 verbatim offsets, 32s longer (intro).
DELETE FROM items WHERE id=233;

-- Communion messages were a real recurring format -- short meditations given
-- before the Lord's Supper -- but the collection had been emptied by the dedupe
-- and nothing else was ever attached. Identified by the preacher naming
-- communion in the opening ("for communion, turn to John 13").
UPDATE items SET collection_id=(SELECT id FROM collections WHERE slug='communion-message')
  WHERE id IN (23,41,70,72);

-- john-13's only member was a duplicate and is gone; drop the empty collection.
DELETE FROM collections WHERE slug='john-13' AND id NOT IN (SELECT collection_id FROM items WHERE collection_id IS NOT NULL);
