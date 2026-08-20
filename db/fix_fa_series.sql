-- The "Refuting the Friendly Atheist" run: 10 episodes working through the
-- blog post "40 Problems with Christianity", but only 2 were ever attached to
-- the collection. The rest were identifiable only from the transcript, since
-- their titles name the topic ("Evolution", "The Judas Problem") rather than
-- the series. series_part is the problem number the episode answers, taken from
-- the episode itself ("we're on problem number 12"). Three are topical
-- spin-offs inside the run that never state a number, so they get no part label.
UPDATE items SET collection_id=(SELECT id FROM collections WHERE slug='refuting-the-friendly-atheist')
  WHERE id IN (272,274,275,276,278,279,282,283);
UPDATE items SET series_part='Problems 1-4' WHERE id=267;
UPDATE items SET series_part='Problems 5-7' WHERE id=268;
UPDATE items SET series_part='Problem 12'   WHERE id=275;
UPDATE items SET series_part='Problem 16'   WHERE id=276;
UPDATE items SET series_part='Problem 21'   WHERE id=278;
UPDATE items SET series_part='Problem 25'   WHERE id=282;
UPDATE items SET series_part='Problem 27'   WHERE id=283;
