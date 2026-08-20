-- Remove 40 raw-recorder duplicate items (DM6204xx).
-- Each is transcript-identical to a properly titled+dated sermon that
-- keeps its own audio; verified all 40 survivors exist in R2 first.
-- item_transcripts and scripture_refs cascade; items_fts_ad clears item_fts.
DELETE FROM items WHERE id IN (138,139,140,141,142,143,144,146,147,148,149,150,151,152,153,154,155,156,158,159,160,161,162,163,164,165,166,167,168,169,170,171,172,173,174,175,176,254,255,256);
