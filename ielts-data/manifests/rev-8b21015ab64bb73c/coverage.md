# IELTS coverage 全量汇总（coverage.md）

- schema: `ielts.coverage/1` version: `coverage/1.0.0`
- generated_at_utc: 2026-10-04T17:20:35.558Z
- run_id: 20261003T140007Z-repair
- data_dir: C:\Users\weo\Desktop\api\ielts-data
- dataset_revision: rev-8b21015ab64bb73c
- source JSON: manifests/rev-8b21015ab64bb73c/coverage.json sha256=7f1de9025cfa918c9f013ee5fa034b1c55ed912e17bdaa6af812803d26f9d7c7
- warnings: []

## 单元状态（370 units = 21 books）

| status | count |
|---|---|
| complete | 0 |
| partial | 168 |
| source_missing | 0 |
| not_extracted | 154 |
| unverified | 48 |

- units: 370 ｜ books: 21
- fully_complete_units: 0
- units_with_audio_verified: 4
- units_with_alignment_complete: 0
- books_pdf_complete: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19

## by skill/variant

| key | units | fully_complete | audio_verified | alignment_complete |
|---|---|---|---|---|
| reading/academic | 84 | 0 | 0 | 0 |
| listening/shared | 84 | 0 | 4 | 0 |
| writing/academic | 84 | 0 | 0 | 0 |
| speaking/shared | 84 | 0 | 0 | 0 |
| reading/general | 17 | 0 | 0 | 0 |
| writing/general | 17 | 0 | 0 | 0 |

## by book

| book | units | fully_complete | pdf_complete |
|---|---|---|---|
| 1 | 18 | 0 | true |
| 2 | 20 | 0 | true |
| 3 | 20 | 0 | true |
| 4 | 20 | 0 | true |
| 5 | 20 | 0 | true |
| 6 | 20 | 0 | true |
| 7 | 20 | 0 | true |
| 8 | 20 | 0 | true |
| 9 | 16 | 0 | true |
| 10 | 20 | 0 | true |
| 11 | 16 | 0 | true |
| 12 | 16 | 0 | true |
| 13 | 16 | 0 | true |
| 14 | 16 | 0 | true |
| 15 | 16 | 0 | true |
| 16 | 16 | 0 | true |
| 17 | 16 | 0 | true |
| 18 | 16 | 0 | true |
| 19 | 16 | 0 | true |
| 20 | 16 | 0 | false |
| 21 | 16 | 0 | false |

## 全量单元明细（370 units）

| unit_id | status | status_reasons | expected | observed | missing | extra | source |
|---|---|---|---|---|---|---|---|
| cambridge:1:shared:listening:1 | partial | content_incomplete; empty_answers:1; unknown_types:1; official_unverified:0/41; audio_verified:0/4; alignment_verified:0/41 | 41 | 41 | 0 | 0 | pte-raw |
| cambridge:1:academic:reading:1 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:1:shared:speaking:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:1:academic:writing:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:1:shared:listening:2 | partial | content_incomplete; missing_assets:1; scripts_available:0/4; empty_answers:2; unknown_types:2; official_unverified:0/41; audio_verified:0/4; alignment_verified:0/41 | 41 | 41 | 0 | 0 | pte-raw |
| cambridge:1:academic:reading:2 | partial | content_incomplete; empty_answers:1; unknown_types:5; official_unverified:0/41 | 41 | 41 | 0 | 0 | pte-raw |
| cambridge:1:shared:speaking:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:1:academic:writing:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:1:shared:listening:3 | partial | content_incomplete; official_unverified:0/42; audio_verified:0/4; alignment_verified:0/42 | 42 | 42 | 0 | 0 | pte-raw |
| cambridge:1:academic:reading:3 | partial | official_unverified:0/38 | 38 | 38 | 0 | 0 | pte-raw |
| cambridge:1:shared:speaking:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:1:academic:writing:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:1:shared:listening:4 | partial | content_incomplete; empty_answers:2; unknown_types:8; official_unverified:0/42; audio_verified:0/4; alignment_verified:0/42 | 42 | 42 | 0 | 0 | pte-raw |
| cambridge:1:academic:reading:4 | partial | official_unverified:0/39 | 39 | 39 | 0 | 0 | pte-raw |
| cambridge:1:shared:speaking:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:1:academic:writing:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:1:general:reading:gta | not_extracted | content_not_indexed | 41 | 0 | 41 | 0 |  |
| cambridge:1:general:writing:gta | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:2:shared:listening:1 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:2:academic:reading:1 | partial | content_incomplete; official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:2:shared:speaking:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:2:academic:writing:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:2:shared:listening:2 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:2:academic:reading:2 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:2:shared:speaking:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:2:academic:writing:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:2:shared:listening:3 | partial | content_incomplete; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:2:academic:reading:3 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:2:shared:speaking:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:2:academic:writing:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:2:shared:listening:4 | partial | content_incomplete; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:2:academic:reading:4 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:2:shared:speaking:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:2:academic:writing:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:2:general:reading:gta | not_extracted | content_not_indexed | 40 | 0 | 40 | 0 |  |
| cambridge:2:general:writing:gta | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:2:general:reading:gtb | not_extracted | content_not_indexed | 40 | 0 | 40 | 0 |  |
| cambridge:2:general:writing:gtb | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:3:shared:listening:1 | partial | content_incomplete; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:3:academic:reading:1 | partial | content_incomplete; official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:3:shared:speaking:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:3:academic:writing:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:3:shared:listening:2 | partial | content_incomplete; scripts_available:0/4; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pdf-extract |
| cambridge:3:academic:reading:2 | partial | content_incomplete; unknown_types:5; official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:3:shared:speaking:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:3:academic:writing:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:3:shared:listening:3 | partial | scripts_available:0/4; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pdf-extract |
| cambridge:3:academic:reading:3 | partial | content_incomplete; official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:3:shared:speaking:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:3:academic:writing:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:3:shared:listening:4 | partial | content_incomplete; scripts_available:0/4; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pdf-extract |
| cambridge:3:academic:reading:4 | partial | content_incomplete; official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:3:shared:speaking:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:3:academic:writing:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:3:general:reading:gta | not_extracted | content_not_indexed | 40 | 0 | 40 | 0 |  |
| cambridge:3:general:writing:gta | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:3:general:reading:gtb | not_extracted | content_not_indexed | 40 | 0 | 40 | 0 |  |
| cambridge:3:general:writing:gtb | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:4:shared:listening:1 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:4:academic:reading:1 | partial | content_incomplete; official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:4:shared:speaking:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:4:academic:writing:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:4:shared:listening:2 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:4:academic:reading:2 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:4:shared:speaking:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:4:academic:writing:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:4:shared:listening:3 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:4:academic:reading:3 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:4:shared:speaking:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:4:academic:writing:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:4:shared:listening:4 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:4:academic:reading:4 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:4:shared:speaking:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:4:academic:writing:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:4:general:reading:gta | not_extracted | content_not_indexed | 40 | 0 | 40 | 0 |  |
| cambridge:4:general:writing:gta | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:4:general:reading:gtb | not_extracted | content_not_indexed | 40 | 0 | 40 | 0 |  |
| cambridge:4:general:writing:gtb | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:5:shared:listening:1 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:5:academic:reading:1 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:5:shared:speaking:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:5:academic:writing:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:5:shared:listening:2 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:5:academic:reading:2 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:5:shared:speaking:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:5:academic:writing:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:5:shared:listening:3 | partial | content_incomplete; missing_assets:3; scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:5:academic:reading:3 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:5:shared:speaking:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:5:academic:writing:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:5:shared:listening:4 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:5:academic:reading:4 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:5:shared:speaking:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:5:academic:writing:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:5:general:reading:gta | not_extracted | content_not_indexed | 40 | 0 | 40 | 0 |  |
| cambridge:5:general:writing:gta | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:5:general:reading:gtb | not_extracted | content_not_indexed | 40 | 0 | 40 | 0 |  |
| cambridge:5:general:writing:gtb | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:6:shared:listening:1 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:6:academic:reading:1 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:6:shared:speaking:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:6:academic:writing:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:6:shared:listening:2 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:6:academic:reading:2 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:6:shared:speaking:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:6:academic:writing:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:6:shared:listening:3 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:6:academic:reading:3 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:6:shared:speaking:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:6:academic:writing:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:6:shared:listening:4 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:6:academic:reading:4 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:6:shared:speaking:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:6:academic:writing:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:6:general:reading:gta | not_extracted | content_not_indexed | 40 | 0 | 40 | 0 |  |
| cambridge:6:general:writing:gta | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:6:general:reading:gtb | not_extracted | content_not_indexed | 40 | 0 | 40 | 0 |  |
| cambridge:6:general:writing:gtb | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:7:shared:listening:1 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:7:academic:reading:1 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:7:shared:speaking:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:7:academic:writing:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:7:shared:listening:2 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:7:academic:reading:2 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:7:shared:speaking:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:7:academic:writing:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:7:shared:listening:3 | partial | content_incomplete; scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:7:academic:reading:3 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:7:shared:speaking:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:7:academic:writing:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:7:shared:listening:4 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:7:academic:reading:4 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:7:shared:speaking:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:7:academic:writing:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:7:general:reading:gta | not_extracted | content_not_indexed | 40 | 0 | 40 | 0 |  |
| cambridge:7:general:writing:gta | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:7:general:reading:gtb | not_extracted | content_not_indexed | 40 | 0 | 40 | 0 |  |
| cambridge:7:general:writing:gtb | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:8:shared:listening:1 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:8:academic:reading:1 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:8:shared:speaking:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:8:academic:writing:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:8:shared:listening:2 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:8:academic:reading:2 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:8:shared:speaking:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:8:academic:writing:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:8:shared:listening:3 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:8:academic:reading:3 | partial | content_incomplete; unknown_types:4; official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:8:shared:speaking:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:8:academic:writing:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:8:shared:listening:4 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:8:academic:reading:4 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:8:shared:speaking:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:8:academic:writing:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:8:general:reading:gta | not_extracted | content_not_indexed | 40 | 0 | 40 | 0 |  |
| cambridge:8:general:writing:gta | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:8:general:reading:gtb | not_extracted | content_not_indexed | 40 | 0 | 40 | 0 |  |
| cambridge:8:general:writing:gtb | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:9:shared:listening:1 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:9:academic:reading:1 | partial | content_incomplete; missing_assets:6; answer_conflicts:2; official_unverified:6/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:9:shared:speaking:1 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:9:academic:writing:1 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:9:shared:listening:2 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:9:academic:reading:2 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:9:shared:speaking:2 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:9:academic:writing:2 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:9:shared:listening:3 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:9:academic:reading:3 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:9:shared:speaking:3 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:9:academic:writing:3 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:9:shared:listening:4 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:9:academic:reading:4 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:9:shared:speaking:4 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:9:academic:writing:4 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:10:shared:listening:1 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:10:academic:reading:1 | partial | empty_answers:1; official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:10:shared:speaking:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:10:academic:writing:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:10:shared:listening:2 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:10:academic:reading:2 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:10:shared:speaking:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:10:academic:writing:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:10:shared:listening:3 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:10:academic:reading:3 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:10:shared:speaking:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:10:academic:writing:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:10:shared:listening:4 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:10:academic:reading:4 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:10:shared:speaking:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:10:academic:writing:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:10:general:reading:gta | not_extracted | content_not_indexed | 40 | 0 | 40 | 0 |  |
| cambridge:10:general:writing:gta | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:10:general:reading:gtb | not_extracted | content_not_indexed | 40 | 0 | 40 | 0 |  |
| cambridge:10:general:writing:gtb | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:11:shared:listening:1 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:11:academic:reading:1 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:11:shared:speaking:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:11:academic:writing:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:11:shared:listening:2 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:11:academic:reading:2 | partial | content_incomplete; unknown_types:7; official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:11:shared:speaking:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:11:academic:writing:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:11:shared:listening:3 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:11:academic:reading:3 | partial | content_incomplete; unknown_types:5; official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:11:shared:speaking:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:11:academic:writing:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:11:shared:listening:4 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:11:academic:reading:4 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:11:shared:speaking:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:11:academic:writing:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:12:shared:listening:5 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:12:academic:reading:5 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:12:shared:speaking:5 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:12:academic:writing:5 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:12:shared:listening:6 | partial | content_incomplete; missing_assets:5; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:12:academic:reading:6 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:12:shared:speaking:6 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:12:academic:writing:6 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:12:shared:listening:7 | partial | content_incomplete; unknown_types:6; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:12:academic:reading:7 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:12:shared:speaking:7 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:12:academic:writing:7 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:12:shared:listening:8 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:12:academic:reading:8 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:12:shared:speaking:8 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:12:academic:writing:8 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:13:shared:listening:1 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:13:academic:reading:1 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:13:shared:speaking:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:13:academic:writing:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:13:shared:listening:2 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:13:academic:reading:2 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:13:shared:speaking:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:13:academic:writing:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:13:shared:listening:3 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:13:academic:reading:3 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:13:shared:speaking:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:13:academic:writing:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:13:shared:listening:4 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:13:academic:reading:4 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:13:shared:speaking:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:13:academic:writing:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:14:shared:listening:1 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:14:academic:reading:1 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:14:shared:speaking:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:14:academic:writing:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:14:shared:listening:2 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:14:academic:reading:2 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:14:shared:speaking:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:14:academic:writing:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:14:shared:listening:3 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:14:academic:reading:3 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:14:shared:speaking:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:14:academic:writing:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:14:shared:listening:4 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:14:academic:reading:4 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:14:shared:speaking:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:14:academic:writing:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:15:shared:listening:1 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:15:academic:reading:1 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:15:shared:speaking:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:15:academic:writing:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:15:shared:listening:2 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:15:academic:reading:2 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:15:shared:speaking:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:15:academic:writing:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:15:shared:listening:3 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:15:academic:reading:3 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:15:shared:speaking:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:15:academic:writing:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:15:shared:listening:4 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:15:academic:reading:4 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:15:shared:speaking:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:15:academic:writing:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:16:shared:listening:1 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:16:academic:reading:1 | partial | content_incomplete; missing_assets:6; official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:16:shared:speaking:1 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:16:academic:writing:1 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:16:shared:listening:2 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:16:academic:reading:2 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:16:shared:speaking:2 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:16:academic:writing:2 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:16:shared:listening:3 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:16:academic:reading:3 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:16:shared:speaking:3 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:16:academic:writing:3 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:16:shared:listening:4 | partial | scripts_available:0/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:16:academic:reading:4 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:16:shared:speaking:4 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:16:academic:writing:4 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:17:shared:listening:1 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:17:academic:reading:1 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:17:shared:speaking:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:17:academic:writing:1 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:17:shared:listening:2 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:17:academic:reading:2 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:17:shared:speaking:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:17:academic:writing:2 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:17:shared:listening:3 | partial | content_incomplete; unknown_types:3; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:17:academic:reading:3 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:17:shared:speaking:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:17:academic:writing:3 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:17:shared:listening:4 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:17:academic:reading:4 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:17:shared:speaking:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:17:academic:writing:4 | not_extracted | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:18:shared:listening:1 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:18:academic:reading:1 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:18:shared:speaking:1 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:18:academic:writing:1 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:18:shared:listening:2 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:18:academic:reading:2 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:18:shared:speaking:2 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:18:academic:writing:2 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:18:shared:listening:3 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:18:academic:reading:3 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:18:shared:speaking:3 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:18:academic:writing:3 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:18:shared:listening:4 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:18:academic:reading:4 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:18:shared:speaking:4 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:18:academic:writing:4 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:19:shared:listening:1 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:19:academic:reading:1 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:19:shared:speaking:1 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:19:academic:writing:1 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:19:shared:listening:2 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:19:academic:reading:2 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:19:shared:speaking:2 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:19:academic:writing:2 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:19:shared:listening:3 | partial | content_incomplete; missing_assets:5; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:19:academic:reading:3 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:19:shared:speaking:3 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:19:academic:writing:3 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:19:shared:listening:4 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:19:academic:reading:4 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:19:shared:speaking:4 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:19:academic:writing:4 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:20:shared:listening:1 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:20:academic:reading:1 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:20:shared:speaking:1 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:20:academic:writing:1 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:20:shared:listening:2 | partial | scripts_available:3/4; official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:20:academic:reading:2 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:20:shared:speaking:2 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:20:academic:writing:2 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:20:shared:listening:3 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:20:academic:reading:3 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:20:shared:speaking:3 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:20:academic:writing:3 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:20:shared:listening:4 | partial | official_unverified:0/40; audio_verified:0/4; alignment_verified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:20:academic:reading:4 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | pte-raw |
| cambridge:20:shared:speaking:4 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:20:academic:writing:4 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:21:shared:listening:1 | partial | official_unverified:0/40; alignment_verified:13/40 | 40 | 40 | 0 | 0 | cam21-html |
| cambridge:21:academic:reading:1 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | cam21-html |
| cambridge:21:shared:speaking:1 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:21:academic:writing:1 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:21:shared:listening:2 | partial | official_unverified:0/40; alignment_verified:15/40 | 40 | 40 | 0 | 0 | cam21-html |
| cambridge:21:academic:reading:2 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | cam21-html |
| cambridge:21:shared:speaking:2 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:21:academic:writing:2 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:21:shared:listening:3 | partial | official_unverified:0/40; alignment_verified:19/40 | 40 | 40 | 0 | 0 | cam21-html |
| cambridge:21:academic:reading:3 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | cam21-html |
| cambridge:21:shared:speaking:3 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:21:academic:writing:3 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:21:shared:listening:4 | partial | official_unverified:0/40; alignment_verified:19/40 | 40 | 40 | 0 | 0 | cam21-html |
| cambridge:21:academic:reading:4 | partial | official_unverified:0/40 | 40 | 40 | 0 | 0 | cam21-html |
| cambridge:21:shared:speaking:4 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |
| cambridge:21:academic:writing:4 | unverified | open_response_or_not_extracted | 0 | 0 | 0 | 0 |  |

- total units rendered: 370
- 生成方式: ielts-data/runs/20261003T140007Z-repair/scratch/gen-coverage-md.py（读取 manifests/rev-8b21015ab64bb73c/coverage.json 原样渲染，不改数值）
