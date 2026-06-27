"""Per-source-file metadata corrections, keyed by the audio file STEM (filename
without extension). Applied by import_catalog.py over the auto-derived metadata.
Fields (all optional): title, recorded_on (YYYY-MM-DD), speaker, collection,
category, passage (display + primary scripture ref; may be book-level like '1 John'),
series_part (short label of where the message falls in a structured series, e.g.
'1st Commandment · Part 1', 'Introduction'), drop (True -> skip this file entirely;
for duplicates the auto-dedupe can't catch because the filenames are unrelated).
"""
OVERRIDES = {
    # Duplicate recording of "Elder Qualifications - Part 2" (2022-06-12), saved
    # under the raw recorder name DM620479.MP3. The titles are unrelated so the
    # (title, year) dedupe can't merge it — drop it explicitly.
    "DM620479": {"drop": True},
    # Elder Qualifications - Part 2: the transcript-frequency heuristic mis-picked
    # Mark 11; the sermon's main text is 1 Timothy 3. (Audio is dropped via
    # redactions.py — published as transcript-only.)
    # ...and it was wrongly filed under "The Ten Commandments" (its ID3 album);
    # it's the week after that series ended. Part 1 has no collection, so clear it.
    "20220612ElderQualsPart2": {"passage": "1 Timothy 3", "collection": None},
    # Raw recorder copy of the 1 John Review — same recording as 20251228LBCSS1John;
    # this metadata makes it dedupe-merge into the published Review.
    "251228_0937": {
        "title": "1 John Review", "recorded_on": "2025-12-28",
        "speaker": "Michael Coughlin", "collection": "1 John",
        "category": "class", "passage": "1 John",
    },
    "20251228LBCSS1John": {"passage": "1 John"},  # the published Review — book-level main text
    # Open-air preaching that aired on the podcast — file by content type.
    "BAB 006 Homosexual Pride Parade Preaching June 2019": {"category": "open_air"},
    "BAB 074 Hunger and Thirst": {
        "passage": "Matthew 5:6",
        # context-targeted (don't touch "Matthew 5, 6, and 7" earlier in the transcript)
        "replace_text": [["But in Matthew 5, 6,", "But in Matthew 5:6,"]],
    },

    # --- The Ten Commandments (Exodus 20) series ----------------------------
    # series_part = which commandment the message expounds; passage = the actual
    # opening Scripture reading / main text (the auto-derived passage was often a
    # transcript-frequency guess that was never read aloud, e.g. Ezekiel 23).
    # The Decalogue is numbered in the Reformed (1689) tradition the series uses.
    "2021-08-01 - Sunday Service - 10 Commandments Intro - Michael Coughlin (731211210526367)_73kbps": {"passage": "Exodus 20:1-17", "series_part": "Introduction"},  # 2021-08-01 10 Commandments Intro
    "2021-08-08 - Sunday Service - New Covenant Commandments - Michael Coughlin (87212213377297)_72kbps": {"passage": "Exodus 20:1-17", "series_part": "Introduction"},  # 2021-08-08 New Covenant Commandments
    "2021-08-15 - Sunday Service - The Ten Commandments - Holy.. - Michael Coughlin (816212043484840)_63kbps": {"passage": "Exodus 20:1-17", "series_part": "Preface"},  # 2021-08-15 The Ten Commandments - Preface
    "2021-08-22 - Sunday Service - The First Commandment - Part 1 - Michael Coughlin (82421011567601)_74kbps": {"passage": "Exodus 20:1-17", "series_part": "1st Commandment - Part 1"},  # 2021-08-22 The First Commandment - Part 1
    "2021-08-29 - Sunday Service - The First Commandment.. - Michael Coughlin (83021211614687)_73kbps": {"passage": "Exodus 20:1-3", "series_part": "1st Commandment - Part 2"},  # 2021-08-29 The First Commandment - Part 2
    "2021-09-05 - Sunday Service - Love God, Love Your Brother - Michael Coughlin (99211110381439)_73kbps": {"passage": "Matthew 22:36-40", "series_part": "1st Commandment - Part 3"},  # 2021-09-05 Love Your Neighbor
    "2021-09-12 - Sunday Service - The Second Commandment.. - Michael Coughlin (914211240173648)_63kbps": {"passage": "Exodus 20:4-6", "series_part": "2nd Commandment - Part 1"},  # 2021-09-12 The Second Commandment..
    "2021-09-19 - Sunday Service - Idols are Worthless - Michael Coughlin (923211225251083)_73kbps": {"passage": "Exodus 20:4-6", "series_part": "2nd Commandment - Part 2"},  # 2021-09-19 Idols are Worthless
    "2021-09-26 - Sunday Service - God's Jealousy - Michael Coughlin (926212354366944)_74kbps": {"passage": "Exodus 20:4-6", "series_part": "2nd Commandment - Part 3"},  # 2021-09-26 God's Jealousy
    "2021-10-03 - Sunday Service - Images of Christ - Michael Coughlin (10721018246207)_74kbps": {"passage": "Exodus 20:4-6", "series_part": "2nd Commandment - Part 4"},  # 2021-10-03 Images of Christ
    "2021-10-10 - Sunday Service - The Seriousnes of Blasphemy - Michael Coughlin (10112111603991)_63kbps": {"passage": "Exodus 20:7", "series_part": "3rd Commandment - Part 1"},  # 2021-10-10 The Seriousnes of Blasphemy
    "2021-10-17 - Sunday Service - Forms of Blasphemy - Michael Coughlin (101721179161978)_73kbps": {"passage": "Exodus 20:7", "series_part": "3rd Commandment - Part 2"},  # 2021-10-17 Forms of Blasphemy
    "2021-10-24 - Sunday Service - Remember the Sabbath - Michael Coughlin (1025211054473473)_73kbps": {"passage": "Exodus 20:8-11", "series_part": "4th Commandment - Part 1"},  # 2021-10-24 Remember the Sabbath
    "2021-10-31 - Sunday Service - Sticks and Stones - Michael Coughlin (111211136135758)_72kbps": {"passage": "Numbers 15:32-36", "series_part": "4th Commandment - Part 2"},  # 2021-10-31 Sticks and Stones
    "2021-11-21 - Sunday Service - Profaning the Sabbath - Part 1 - Michael Coughlin (112321165944133)_72kbps": {"passage": "Exodus 20:8-11", "series_part": "4th Commandment - Part 3"},  # 2021-11-21 Profaning the Sabbath - Part 1
    "2021-11-28 - Sunday Service - Profaning the Sabbath - Part 2 - Michael Coughlin (127211648226040)_65kbps": {"passage": "Matthew 12:1-8", "series_part": "4th Commandment - Part 4"},  # 2021-11-28 Profaning the Sabbath - Part 2
    "2021-12-05 - Sunday Service - Abortion and the Bible - Michael Coughlin (12821234042478)_73kbps": {"passage": "Exodus 21:22-23", "series_part": "6th Commandment"},  # 2021-12-05 Abortion and the Bible (preached early, under the 6th)
    "2021-12-19 - Sunday Service - The Sunday Sabbath - Michael Coughlin (1221211535121856)_73kbps": {"passage": "John 20:19-29", "series_part": "4th Commandment - Part 5"},  # 2021-12-19 The Sunday Sabbath
    "2021-12-26 - Sunday Service - Did Jesus Break the 5th_ - Michael Coughlin (1229211633587562)_74kbps": {"passage": "Exodus 20:12", "series_part": "5th Commandment - Part 1"},  # 2021-12-26 Did Jesus Break the 5th?
    "2022-01-02 - Sunday Service - The 5th Commandment Applied - Michael Coughlin (1622115084997)_72kbps": {"passage": "Exodus 20:12", "series_part": "5th Commandment - Part 2"},  # 2022-01-02 The 5th Commandment Applied
    "2022-01-09 - Sunday Service - Submission is for Adults Too - Michael Coughlin (110221337184012)_72kbps": {"passage": "Romans 13:1-7", "series_part": "5th Commandment - Part 3"},  # 2022-01-09 Submission is for Adults Too
    "2022-01-30 - Sunday Service - Humility is the Key - Michael Coughlin (1302215432496)_74kbps": {"passage": "Exodus 20:12", "series_part": "5th Commandment - Part 4"},  # 2022-01-30 Humility is the Key
    "2022-02-06 - Sunday Service - We Should Not Be Like Cain - Michael Coughlin (27221152193642)_73kbps": {"passage": "Genesis 4:1-10", "series_part": "6th Commandment - Part 1"},  # 2022-02-06 We Should Not Be Like Cain
    "2022-02-13 - Sunday Service - Sanctuary Cities - Michael Coughlin (215221216363058)_76kbps": {"passage": "Numbers 35:16-34", "series_part": "6th Commandment - Part 2"},  # 2022-02-13 Sanctuary Cities
    "2022-02-20 - Sunday Service - Worship & Murder - Michael Coughlin (22122169344033)_72kbps": {"passage": "Matthew 5:21-26", "series_part": "6th Commandment - Part 3"},  # 2022-02-20 Worship & Murder
    "2022-02-27 - Sunday Service - Racism, Abortion, Gossip.. - Michael Coughlin (228222328245251)_73kbps": {"passage": "Matthew 27:1-5", "series_part": "6th Commandment - Part 4"},  # 2022-02-27 Racism, Abortion, Gossip, Suicide
    "2022-03-06 - Sunday Service - Marriage Before Adultery - Michael Coughlin (3102212216507)_73kbps": {"passage": "Genesis 2:18-25", "series_part": "7th Commandment - Part 1"},  # 2022-03-06 Marriage Before Adultery
    "2022-03-13 - Sunday Service - Lust of the Eye - Michael Coughlin (31422112186513)_71kbps": {"passage": "Matthew 5:27-30", "series_part": "7th Commandment - Part 2"},  # 2022-03-13 Lust of the Eye
    "2022-03-27 - Sunday Service - God Hates Divorce - Michael Coughlin (32822112385295)_73kbps": {"passage": "Matthew 19:3-9", "series_part": "7th Commandment - Part 3"},  # 2022-03-27 God Hates Divorce
    "2022-04-03 - Sunday Service - Does the Bible Whisper_ - Michael Coughlin (47222317447011)_72kbps": {"passage": "Ephesians 5:3-14", "series_part": "7th Commandment - Part 4"},  # 2022-04-03 Does the Bible Whisper?
    "2022-04-10 - Sunday Service - But Rather - Michael Coughlin (411221130111956)_64kbps": {"passage": "Ephesians 4:28", "series_part": "8th Commandment - Part 1"},  # 2022-04-10 But Rather
    "2022-04-17 - Sunday Service - Stealing from God_ - Michael Coughlin (41822182221436)_74kbps": {"passage": "Deuteronomy 22:1-4", "series_part": "8th Commandment - Part 2"},  # 2022-04-17 Stealing from God?
    "2022-04-24 - Sunday Service - We Are All Witnesses - Michael Coughlin (425222212554791)_73kbps": {"passage": "Exodus 20:16", "series_part": "9th Commandment - Part 1"},  # 2022-04-24 We Are All Witnesses
    "2022-05-01 - Sunday Service - How to Define Lying - Michael Coughlin (53222252242576)_73kbps": {"passage": "Exodus 1:15-21", "series_part": "9th Commandment - Part 2"},  # 2022-05-01 How to Define Lying
    "2022-05-08 - Sunday Service - Inward Motions of Sin - Michael Coughlin (51222137516752)_73kbps": {"passage": "Exodus 20:17", "series_part": "10th Commandment - Part 1"},  # 2022-05-08 Inward Motions of Sin
    "2022-05-16 - Sunday Service - When Lust Conceives - Michael Coughlin (52022107172145)_73kbps": {"passage": "James 1:13-15", "series_part": "10th Commandment - Part 2"},  # 2022-05-16 When Lust Conceives
    "2022-05-22 - Sunday Service - Seek the Kingdom - Michael Coughlin (523222133592664)_72kbps": {"passage": "Matthew 6:24-34", "series_part": "10th Commandment - Part 3"},  # 2022-05-22 Seek the Kingdom
    "2022-05-29 - Sunday Service - Godliness Actually Is Gain - Michael Coughlin (530221318183430)_69kbps": {"passage": "1 Timothy 6:17-19", "series_part": "10th Commandment - Part 4"},  # 2022-05-29 Godliness Actually Is Gain
    # Duplicate recordings (raw re-uploads with off dates) of the feed-correct
    # cbcoh copies above — drop so the series isn't doubled up.
    "202111226JesusTheBoy": {"drop": True},      # dup of "Did Jesus Break the 5th?" (2021-12-26)
    "20220104HonorYourParents": {"drop": True},  # dup of "The 5th Commandment Applied" (2022-01-02)
    "CoarseJestingFinal": {"drop": True},        # dup of "Does the Bible Whisper?" (2022-04-03)
}
