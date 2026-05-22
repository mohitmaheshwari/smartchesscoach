# Residual LOW captions — engine-speak floor

These captions are not bugs. They fire when:
- cp_loss 100-249 (mistake tier)
- No tactical / positional detector matches
- User is in a balanced position

Two variants make up the entire 79-caption set:

- **why_user_reply** — "Opponent's strongest reply: X." — 59 positions
- **why_user_missed_material** — "X wins material in the resulting line." — 20 positions

## Per-position files (capped at 20 per variant for review tractability)

- [001_reply_dfe3e5c8_m4_g6.md](001_reply_dfe3e5c8_m4_g6.md) — `why_user_reply` `dfe3e5c8 m4 g6` cp=149
- [002_reply_dfe3e5c8_m5_Bg7.md](002_reply_dfe3e5c8_m5_Bg7.md) — `why_user_reply` `dfe3e5c8 m5 Bg7` cp=114
- [003_reply_fc97ee1d_m8_Bc4.md](003_reply_fc97ee1d_m8_Bc4.md) — `why_user_reply` `fc97ee1d m8 Bc4` cp=217
- [004_reply_fc97ee1d_m9_Bd3.md](004_reply_fc97ee1d_m9_Bd3.md) — `why_user_reply` `fc97ee1d m9 Bd3` cp=106
- [005_reply_61895f5a_m12_Ba3.md](005_reply_61895f5a_m12_Ba3.md) — `why_user_reply` `61895f5a m12 Ba3` cp=215
- [006_reply_c25fea91_m19_Kf8.md](006_reply_c25fea91_m19_Kf8.md) — `why_user_reply` `c25fea91 m19 Kf8` cp=179
- [007_reply_c25fea91_m20_Qe6.md](007_reply_c25fea91_m20_Qe6.md) — `why_user_reply` `c25fea91 m20 Qe6` cp=321
- [008_reply_f4125049_m5_Qf6.md](008_reply_f4125049_m5_Qf6.md) — `why_user_reply` `f4125049 m5 Qf6` cp=144
- [009_reply_64e3c103_m4_Nc3.md](009_reply_64e3c103_m4_Nc3.md) — `why_user_reply` `64e3c103 m4 Nc3` cp=192
- [010_reply_849d1899_m34_a4.md](010_reply_849d1899_m34_a4.md) — `why_user_reply` `849d1899 m34 a4` cp=159
- [011_reply_a9cd46d0_m14_a3.md](011_reply_a9cd46d0_m14_a3.md) — `why_user_reply` `a9cd46d0 m14 a3` cp=100
- [012_reply_f5a5f58c_m5_d6.md](012_reply_f5a5f58c_m5_d6.md) — `why_user_reply` `f5a5f58c m5 d6` cp=273
- [013_reply_d57e7eea_m7_a6.md](013_reply_d57e7eea_m7_a6.md) — `why_user_reply` `d57e7eea m7 a6` cp=150
- [014_reply_27c79130_m7_d4.md](014_reply_27c79130_m7_d4.md) — `why_user_reply` `27c79130 m7 d4` cp=115
- [015_reply_3e1a1a93_m11_Qa5.md](015_reply_3e1a1a93_m11_Qa5.md) — `why_user_reply` `3e1a1a93 m11 Qa5` cp=156
- [016_reply_e7ce2c88_m8_Be7.md](016_reply_e7ce2c88_m8_Be7.md) — `why_user_reply` `e7ce2c88 m8 Be7` cp=159
- [017_reply_e7ce2c88_m9_exf5.md](017_reply_e7ce2c88_m9_exf5.md) — `why_user_reply` `e7ce2c88 m9 exf5` cp=163
- [018_reply_aa52c973_m7_Bc5.md](018_reply_aa52c973_m7_Bc5.md) — `why_user_reply` `aa52c973 m7 Bc5` cp=100
- [019_reply_aa52c973_m24_Rd7.md](019_reply_aa52c973_m24_Rd7.md) — `why_user_reply` `aa52c973 m24 Rd7` cp=522
- [020_reply_a6b432f5_m8_h6.md](020_reply_a6b432f5_m8_h6.md) — `why_user_reply` `a6b432f5 m8 h6` cp=152
- [021_material_6569e93f_m6_Qe2.md](021_material_6569e93f_m6_Qe2.md) — `why_user_missed_material` `6569e93f m6 Qe2` cp=175
- [022_material_461ece5c_m11_e4.md](022_material_461ece5c_m11_e4.md) — `why_user_missed_material` `461ece5c m11 e4` cp=145
- [023_material_fc97ee1d_m7_Bb5.md](023_material_fc97ee1d_m7_Bb5.md) — `why_user_missed_material` `fc97ee1d m7 Bb5` cp=210
- [024_material_2d5ad07d_m7_Bf1.md](024_material_2d5ad07d_m7_Bf1.md) — `why_user_missed_material` `2d5ad07d m7 Bf1` cp=162
- [025_material_076710d8_m4_d3.md](025_material_076710d8_m4_d3.md) — `why_user_missed_material` `076710d8 m4 d3` cp=120
- [026_material_2bdf179c_m5_Bd3.md](026_material_2bdf179c_m5_Bd3.md) — `why_user_missed_material` `2bdf179c m5 Bd3` cp=102
- [027_material_db4ea92d_m8_b6.md](027_material_db4ea92d_m8_b6.md) — `why_user_missed_material` `db4ea92d m8 b6` cp=116
- [028_material_d57e7eea_m6_Bg4.md](028_material_d57e7eea_m6_Bg4.md) — `why_user_missed_material` `d57e7eea m6 Bg4` cp=180
- [029_material_b84a1c55_m10_a5.md](029_material_b84a1c55_m10_a5.md) — `why_user_missed_material` `b84a1c55 m10 a5` cp=205
- [030_material_fc3914fc_m27_c5.md](030_material_fc3914fc_m27_c5.md) — `why_user_missed_material` `fc3914fc m27 c5` cp=276
- [031_material_fc3914fc_m28_Rf8.md](031_material_fc3914fc_m28_Rf8.md) — `why_user_missed_material` `fc3914fc m28 Rf8` cp=131
- [032_material_70cacf59_m13_Qd7.md](032_material_70cacf59_m13_Qd7.md) — `why_user_missed_material` `70cacf59 m13 Qd7` cp=100
- [033_material_23b2a4f0_m6_Qd2.md](033_material_23b2a4f0_m6_Qd2.md) — `why_user_missed_material` `23b2a4f0 m6 Qd2` cp=105
- [034_material_c80dd5fa_m6_b6.md](034_material_c80dd5fa_m6_b6.md) — `why_user_missed_material` `c80dd5fa m6 b6` cp=203
- [035_material_e6c0ca28_m2_Na6.md](035_material_e6c0ca28_m2_Na6.md) — `why_user_missed_material` `e6c0ca28 m2 Na6` cp=204
- [036_material_9e6941fc_m16_Qe4.md](036_material_9e6941fc_m16_Qe4.md) — `why_user_missed_material` `9e6941fc m16 Qe4` cp=168
- [037_material_fc6a7bad_m4_Bc5.md](037_material_fc6a7bad_m4_Bc5.md) — `why_user_missed_material` `fc6a7bad m4 Bc5` cp=337
- [038_material_8b7d4545_m17_Bd2.md](038_material_8b7d4545_m17_Bd2.md) — `why_user_missed_material` `8b7d4545 m17 Bd2` cp=210
- [039_material_8b282bab_m5_exd5.md](039_material_8b282bab_m5_exd5.md) — `why_user_missed_material` `8b282bab m5 exd5` cp=118
- [040_material_b39642d4_m4_Bc4.md](040_material_b39642d4_m4_Bc4.md) — `why_user_missed_material` `b39642d4 m4 Bc4` cp=126
