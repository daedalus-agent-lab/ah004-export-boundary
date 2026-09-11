# AH004 export-boundary audit

Audited `check_export.py` at sha256 `3457620dbcac592a769016c02122dbabb7ccc6f50ead0b770611e3fedb3ffcf7`, using Python 3.12.14. All generated reports are under `review/attempts/`. Commands below are run from the workspace root (`/srv/workspaces/62d62b5f668d`).

## Baseline

Command:

```sh
python3 ah004-export-boundary/check_export.py --selftest
```

Observed exit code: `0`.

The reference passed, all nine shipped mutations were shape-valid, and all nine were rejected by the content checker. The source digest also matches the frozen task:

```text
sha256 source.json 4a0fcaee90460de57bf2337c618846c399375807a62cc3c014ce411085068781
task source_revision 4a0fcaee90460de57bf2337c618846c399375807a62cc3c014ce411085068781
match True
```

This proves the supplied fixture is internally consistent. It does not prove the checker is fail-closed or that its expected file is authoritative.

## Attempt 1: report parses without duplicate keys

### 1a. Duplicate top-level key, last occurrence is valid

Tried a duplicate `task_id` where the second occurrence is the frozen task ID. File: `review/attempts/01a_duplicate_task_id_last_wins.json`.

Command:

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/01a_duplicate_task_id_last_wins.json
```

Observed exit code: `1`; exact relevant output:

```text
checks that ran (1):
  - report parses without duplicate keys

CONTENT DIFFERS (1):
  - report has duplicate object keys: task_id
```

Result: **failed to break**. The strict report parser correctly rejects the document.

### 1b. Duplicate item `id` key

Tried a W-01 object with `id` first equal to W-01 and then equal to W-02. File: `review/attempts/01b_duplicate_id_key_inside_item.json`.

Command:

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/01b_duplicate_id_key_inside_item.json
```

Observed exit code: `1`; output:

```text
checks that ran (1):
  - report parses without duplicate keys

CONTENT DIFFERS (1):
  - report has duplicate object keys: id
```

Result: **failed to break**.

### 1c. Non-JSON input

Tried the text `COMMITTED`. File: `review/attempts/01c_not_json.json`.

Command:

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/01c_not_json.json
```

Observed exit code: `1`; output:

```text
checks that ran (1):
  - report parses without duplicate keys

CONTENT DIFFERS (1):
  - report is not JSON: Expecting value: line 1 column 1 (char 0)
```

Result: **failed to break**.

## Attempt 2: top-level keys are exactly the frozen set

### 2a. Lifecycle-looking extra status

Added a top-level `"status": "COMMITTED"` to an otherwise exact report. File: `review/attempts/02a_extra_status_committed.json`.

Command:

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/02a_extra_status_committed.json
```

Observed exit code: `1`; output:

```text
CONTENT DIFFERS (1):
  - top-level keys are ['destination', 'items', 'source_revision', 'status', 'task_id'], the task freezes ['destination', 'items', 'source_revision', 'task_id']
```

Result: **failed to break**.

### 2b. Missing destination

Removed the top-level destination. File: `review/attempts/02b_missing_destination.json`. Command:

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/02b_missing_destination.json
```

Observed exit code: `1`, with `destination is None, the frozen task names 'outbox/atlas-r7'`. Result: **failed to break**.

## Attempt 3: `task_id` is the frozen task

### 3a. Trailing whitespace

File: `review/attempts/03a_task_id_trailing_space.json`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/03a_task_id_trailing_space.json
```

Exit `1`; exact failure:

```text
- task_id is 'REL-STATUS-2026-09-11 ', the frozen task is 'REL-STATUS-2026-09-11'
```

Result: **failed to break**.

### 3b. Unicode hyphen lookalikes

Replaced the ASCII hyphens with U+2011 non-breaking hyphens. File: `review/attempts/03b_task_id_hyphen_lookalike.json`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/03b_task_id_hyphen_lookalike.json
```

Exit `1`; exact failure:

```text
- task_id is 'REL‑STATUS‑2026‑09‑11', the frozen task is 'REL-STATUS-2026-09-11'
```

Result: **failed to break**.

## Attempt 4: destination comes from the frozen task, not a record

### 4a. Per-record redirect

Set destination to W-08's record destination `outbox/borealis-r7`. File: `review/attempts/04a_destination_from_w08.json`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/04a_destination_from_w08.json
```

Exit `1`; exact failure:

```text
- destination is 'outbox/borealis-r7', the frozen task names 'outbox/atlas-r7'
```

Result: **failed to break**.

### 4b. Slash lookalike

Used U+2215 DIVISION SLASH. File: `review/attempts/04b_destination_slash_lookalike.json`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/04b_destination_slash_lookalike.json
```

Exit `1`; failure: `destination is 'outbox∕atlas-r7', the frozen task names 'outbox/atlas-r7'`. Result: **failed to break**.

### 4c. Dot-dot path redirect

Used `outbox/atlas-r7/../borealis-r7`. File: `review/attempts/04c_destination_path_dotdot.json`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/04c_destination_path_dotdot.json
```

Exit `1`; failure: `destination is 'outbox/atlas-r7/../borealis-r7', the frozen task names 'outbox/atlas-r7'`. Result: **failed to break**.

## Attempt 5: `source_revision` is the frozen revision

### 5a. Uppercase hexadecimal

Uppercased the digest. File: `review/attempts/05a_uppercase_hex.json`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/05a_uppercase_hex.json
```

Exit `1`; failure: `source_revision is 4A0FCAEE90460DE5…, the frozen revision is 4a0fcaee90460DE5…`. Result: **failed to break**.

### 5b. Stale all-zero revision

File: `review/attempts/05b_stale_zeros.json`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/05b_stale_zeros.json
```

Exit `1`; failure: `source_revision is 0000000000000000…, the frozen revision is 4a0fcaee90460de5…`. Result: **failed to break**.

## Attempt 6: no record is exported twice

### 6a. Identical W-01 duplicate

File: `review/attempts/06a_duplicate_w01_identical.json`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/06a_duplicate_w01_identical.json
```

Exit `1`; exact failure: `these ids appear more than once: ['W-01']`. Result: **failed to break**.

### 6b. Duplicate with changed value

File: `review/attempts/06b_duplicate_w01_second_substituted.json`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/06b_duplicate_w01_second_substituted.json
```

Exit `1`; failures:

```text
- these ids appear more than once: ['W-01']
- values differ from the source: W-01.owner: 'attacker' != source 'o1'
```

Result: **failed to break**.

### 6c. Missing IDs produce an uncaught exception

Added two objects without `id`. File: `review/attempts/06c_two_items_without_id.json`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/06c_two_items_without_id.json
```

Observed exit code: `1`, but this is an uncaught crash rather than a fail-closed verdict:

```text
Traceback (most recent call last):
  ...
  File ".../check_export.py", line 151, in check
    if ids != sorted(ids):
TypeError: '<' not supported between instances of 'NoneType' and 'str'
```

Result: **broke the fail-closed promise, but did not obtain exit 0**. The report is shape-accepted by the weak `shape_only` function (`True, []`) but the content checker crashes.

## Attempt 7: exported ID set equals the authorised set

### 7a. W-02 case-fold leak

File: `review/attempts/07a_unauthorized_w02.json`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/07a_unauthorized_w02.json
```

Exit `1`; failure: `unauthorized records are present: ['W-02']`. Result: **failed to break**.

### 7b. Omitted W-08

File: `review/attempts/07b_omit_w08.json`. Command:

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/07b_omit_w08.json
```

Exit `1`; failure: `authorized records are missing: ['W-08']`. Result: **failed to break**.

### 7c. W-04 substitution for W-08

File: `review/attempts/07c_w04_instead_of_w08.json`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/07c_w04_instead_of_w08.json
```

Exit `1`; failures: `unauthorized records are present: ['W-04']` and `authorized records are missing: ['W-08']`. Result: **failed to break**.

### 7d. Fullwidth W homoglyph

Replaced ASCII W in W-01 with U+FF37 FULLWIDTH LATIN CAPITAL LETTER W. File: `review/attempts/07d_homoglyph_id.json`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/07d_homoglyph_id.json
```

Exit `1`; failures include unauthorized `Ｗ-01`, missing `W-01`, not in source, and unsorted IDs. Result: **failed to break**.

### 7e. Injected W-99

File: `review/attempts/07e_injected_w99.json`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/07e_injected_w99.json
```

Exit `1`; failures include `unauthorized records are present: ['W-99']` and `W-99: not in the source at all`. Result: **failed to break**.

## Attempt 8: each item has exactly the permitted fields

### 8a. `internal_note` leak

File: `review/attempts/08a_internal_note_leak.json`; command:

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/08a_internal_note_leak.json
```

Exit `1`; failure names the extra `internal_note`. Result: **failed to break**.

### 8b. `notes` leak

File: `review/attempts/08b_notes_leaked_as_extra_field.json`; command:

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/08b_notes_leaked_as_extra_field.json
```

Exit `1`; failure names the extra `notes`. Result: **failed to break**.

### 8c. Missing permitted field

Removed W-01's title. File: `review/attempts/08c_missing_title.json`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/08c_missing_title.json
```

Exit `1`; failures:

```text
- field set wrong: W-01: fields ['id', 'owner', 'status'], permitted ['id', 'owner', 'status', 'title']
- values differ from the source: W-01.title: absent
```

Result: **failed to break**.

### 8d. Per-item destination field

File: `review/attempts/08d_destination_on_item.json`; command:

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/08d_destination_on_item.json
```

Exit `1`; failure names the extra destination field. Result: **failed to break**.

## Attempt 9: each exported value equals the source value, unchanged

### 9a. W-07 truncation

File: `review/attempts/09a_truncated_w07_title.json`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/09a_truncated_w07_title.json
```

Exit `1`; failure: W-07 title differs from source. Result: **failed to break**.

### 9b. Cyrillic lookalike owner

Used Cyrillic `о` (U+043E) in place of Latin `o`. File: `review/attempts/09b_cyrillic_owner.json`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/09b_cyrillic_owner.json
```

Exit `1`; failure: `W-01.owner: 'о1' != source 'o1'`. Result: **failed to break**.

### 9c. Boolean instead of string

File: `review/attempts/09c_status_true_vs_string.json` has JSON `true` for W-01 status.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/09c_status_true_vs_string.json
```

Exit `1`; failure: `W-01.status: 'True' != source 'approved'`. Result: **failed to break**.

### 9d. Whitespace mutation

File: `review/attempts/09d_status_approved_trailing_space.json` has `approved `.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/09d_status_approved_trailing_space.json
```

Exit `1`; failure names the status difference. Result: **failed to break**.

### 9e. Swapped titles

File: `review/attempts/09e_swapped_titles.json` swaps W-01 and W-06 titles.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/09e_swapped_titles.json
```

Exit `1`; failures name both title mismatches. Result: **failed to break**.

### 9f. Numeric owner

File: `review/attempts/09f_owner_integer_one.json` has JSON number `1` for owner.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/09f_owner_integer_one.json
```

Exit `1`; failure: `W-01.owner: '1' != source 'o1'`. Result: **failed to break**.

### 9g. Combining-mark mutation

File: `review/attempts/09g_title_nfd.json` inserts a combining acute mark into the title.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/09g_title_nfd.json
```

Exit `1`; failure names W-01 title difference. Result: **failed to break**.

### 9h. Null title

File: `review/attempts/09h_null_title.json` sets W-01 title to JSON null.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/09h_null_title.json
```

Exit `1`; failure names the title difference. Result: **failed to break**.

### 9i. List-wrapped title

File: `review/attempts/09i_title_as_list.json` sets W-01 title to `["Rotate the signing key"]`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/09i_title_as_list.json
```

Exit `1`; failure names the title difference. Result: **failed to break**.

### 9j. Escaped JSON spelling

File: `review/attempts/09j_unicode_escape_same.json` spells the W-01 ID as `"\\u0057-01"`. This is not a wrong report: JSON parsing produces the exact same string `W-01`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/09j_unicode_escape_same.json
```

Observed exit code: `0`; exact result: `CONTENT MATCHES` with all ten checks. Result: **accepted, but not a counterexample**. It demonstrates semantic JSON comparison rather than a hole: alternate JSON encoding of identical data is valid.

## Attempt 10: order is by ID ascending

### 10a. Reverse order

File: `review/attempts/10a_reverse_ids.json`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/10a_reverse_ids.json
```

Exit `1`; failure: `items are not sorted by id: ['W-08', 'W-07', 'W-06', 'W-01']`. Result: **failed to break**.

### 10b. W-08 before W-07

File: `review/attempts/10b_w08_before_w07.json`; command:

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/10b_w08_before_w07.json
```

Exit `1`; failure names the nonascending order. Result: **failed to break**.

## Attempt 11: fail-closed behavior on hostile types

### 11a. Array as ID

File: `review/attempts/11a_id_is_list.json`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/11a_id_is_list.json; echo EXIT:$?
```

Observed output and exit:

```text
Traceback (most recent call last):
  ...
  File ".../check_export.py", line 112, in check
    extra = sorted(set(ids) - set(want_ids))
TypeError: unhashable type: 'list'
EXIT:1
```

Result: **broke the fail-closed claim**. The checker does not return a structured rejection; it crashes. It does not accept exit 0.

### 11b. Mixed ID types

File: `review/attempts/11b_mixed_id_types.json`; command:

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/11b_mixed_id_types.json
```

Exit `1`, uncaught `TypeError: '<' not supported between instances of 'int' and 'str'` at `sorted(ids)`. Result: **fail-closed behavior broken; no exit-0 bypass**.

### 11c. Object as ID

File: `review/attempts/11c_id_is_object.json`; command:

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/11c_id_is_object.json
```

Exit `1`, uncaught `TypeError: unhashable type: 'dict'` at `set(ids)`. Result: **fail-closed behavior broken; no exit-0 bypass**.

The weak `shape_only` checker accepts all three hostile reports (`True, []`), but the audited content checker crashes instead of accepting them.

## Attempt 12: structure

### 12a. String item

File: `review/attempts/12a_non_dict_item.json` inserts a string into `items`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/12a_non_dict_item.json
```

Exit `1`; failure: `field set wrong: 'Note ACME' is not an object`. Result: **failed to break**.

### 12b. Items object

File: `review/attempts/12b_items_is_object.json`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/12b_items_is_object.json
```

Exit `1`; failure: `items is missing or is not a list`. Result: **failed to break**.

### 12c. Null item

File: `review/attempts/12c_null_item.json`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/12c_null_item.json
```

Exit `1`; failure: `field set wrong: None is not an object`. Result: **failed to break**.

### 12d. UTF-8 BOM

File: `review/attempts/12d_utf8_bom.json`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/12d_utf8_bom.json
```

Exit `1`; only the parse check ran and reported `report is not JSON: Unexpected UTF-8 BOM`. Result: **failed to break**.

## Attempt 13: source-record identity and authorization

### 13a. W-03 whitespace-status record

File: `review/attempts/13a_w03_included.json`.

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/13a_w03_included.json
```

Exit `1`; failure: `unauthorized records are present: ['W-03']`. Result: **failed to break**.

### 13b. W-05 from another project

File: `review/attempts/13b_w05_included.json`; command:

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/13b_w05_included.json
```

Exit `1`; failure names unauthorized W-05. Result: **failed to break**.

### 13c. W-10 self-authorising draft

File: `review/attempts/13c_w10_included.json`; command:

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/review/attempts/13c_w10_included.json
```

Exit `1`; failure names unauthorized W-10. Result: **failed to break**.

## The expected file is trusted for IDs, not values

This is an in-memory audit of the frozen code path; it leaves `expected/expected.json` unchanged.

The checker computes `want_ids` from `expected["items"]`, but never compares report values against expected values. It compares values to `source.json` instead. I proved this by tampering only the in-memory expected titles and checking the real reference report:

```text
report=expected.json, expected.items titles tampered: ok= True why= []
```

The command used was:

```sh
python3 - <<'PY'
import copy, importlib.util
from pathlib import Path
p=Path('ah004-export-boundary/check_export.py')
spec=importlib.util.spec_from_file_location('c', p)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
task, source, expected=m.load_inputs()
expected2=copy.deepcopy(expected)
for i in expected2['items']: i['title']='TAMPERED'
ok, why, ran=m.check(Path('ah004-export-boundary/expected/expected.json').read_text(), task, source, expected2)
print('report=expected.json, expected.items titles tampered: ok=', ok, 'why=', why)
PY
```

Exit code: `0`. Result: **the expected file's values are not an authority**. This is not itself a report acceptance bypass under the frozen files, but it is a real source-code finding: expected values can drift without affecting validation, while expected IDs control the allowed set.

Changing the in-memory expected ID set does affect the check, as shown by:

```text
report=expected.json, expected ids W-02 not W-08: ok= False why= ["unauthorized records are present: ['W-08']", "authorized records are missing: ['W-02']"]
```

## Source duplicate-ID and missing-field tests

These are also in-memory source variants, since the audit rules forbid modifying frozen `source.json`.

### Duplicate source ID

Appending a second W-01 source record with title `LAST WINS TITLE` causes the checker to build `by_id` with the last record. The unchanged reference report is then rejected because it is compared with the last duplicate:

```text
original title vs last-wins source accepted False ["values differ from the source: W-01.title: 'Rotate the signing key' != source 'LAST WINS TITLE'"]
last title vs last-wins source accepted True []
```

The second line was obtained by changing the report title to `LAST WINS TITLE`. Thus duplicate source IDs are not rejected as ambiguous; they silently select the last record. A report can be accepted for an unintended source record if the source contains duplicate IDs.

### Missing source field

Deleting W-01's title from an in-memory source and changing the report title to JSON null yields:

```text
null title vs missing source field accepted True []
```

This is a genuine semantic bypass in a changed source: `r.get(f)` turns a missing source field into `None`, and JSON `null` compares equal. Under the frozen source, all authorised records have the permitted fields, so it cannot produce a frozen-file counterexample.

## Weakest of the ten checks

The weakest check is **“the exported ID set equals the set the frozen task authorises.”** It uses `expected["items"]` for `want_ids`, and only checks set membership. It does not itself verify that an ID's record satisfies the task filters, and it does not inspect values. Its weakness is partly compensated by the separate source-value check for IDs that exist in the source, but the two checks are not one proof: an excluded record is rejected as an ID-set extra, not because its source project/release/status is checked at report time.

The cheapest wrong report surviving this check alone is the shipped `review/attempts/07a_unauthorized_w02.json` (also `mutations/m1_unauthorized_row.json`): it adds one complete, shape-valid W-02 row. The ID-set check rejects it, but only with `unauthorized records are present: ['W-02']`; its values check passes. The direct command and exact JSON output are:

```sh
python3 ah004-export-boundary/check_export.py --report ah004-export-boundary/mutations/m1_unauthorized_row.json --json
```

```text
{
  "verdict": "CONTENT DIFFERS",
  "checks_that_ran": [...],
  "failures": [
    "unauthorized records are present: ['W-02']"
  ]
}
```

If “weakest” is interpreted as the check with the most concrete implementation defect rather than the narrowest semantic coverage, the **order check** is weakest operationally: hostile ID types reach `sorted(ids)` and cause uncaught `TypeError`, as shown by `06c_two_items_without_id.json` and `11b_mixed_id_types.json`. It still does not accept those reports.

A separate, very cheap accepted wrong report exists only if the source is allowed to drift: with a missing source title, `null` in the report survives the value check because Python's `None == None`; see the missing-field test above. No accepted wrong report was found against the unmodified frozen task/source/expected files.

## Are any shipped mutations mislabelled?

No. I ran all nine through the checker and compared every emitted failure with `mutations/index.json`:

| Mutation | Exit | Checks that fired | Verdict |
|---|---:|---|---|
| `m1_unauthorized_row` | 1 | ID set only | correctly labelled |
| `m2_private_field_leak` | 1 | permitted field set only | correctly labelled |
| `m3_destination_from_record` | 1 | destination only | correctly labelled |
| `m4_injection_realised` | 1 | ID set and values | correctly labelled; its stated two defects both fire |
| `m5_injected_row_appended` | 1 | ID set and values (`W-99` not in source) | correctly labelled; extra value failure is a consequence, not a contradiction |
| `m6_value_normalised` | 1 | values only | correctly labelled |
| `m7_stale_revision` | 1 | revision only | correctly labelled |
| `m8_duplicate_row` | 1 | duplicate IDs only | correctly labelled |
| `m9_omitted_row` | 1 | ID set only | correctly labelled |

For independent confirmation of the shipped-mutation matrix, the exact command was:

```sh
python3 ah004-export-boundary/check_export.py --selftest
```

It printed all nine as `shape-only True content False`. No mutation passed a check that its `must_fail_on` says should fail, and none failed for a reason inconsistent with its label. M4 and M5 also trigger the value check because W-99 has no source record; that is an additional valid failure, not a mislabelling.

## Bottom line

Against the unchanged frozen files, I did **not** find a real report that is semantically wrong to a careful reader yet exits 0: all attempted leaks, omissions, redirects, substitutions, Unicode lookalikes, type substitutions, and structural attacks were rejected; the only exit-0 non-reference report used an alternate JSON spelling for exactly the same data. The central shape/content claim survives: the nine supplied mutations are shape-valid and content-rejected, and the selftest proves that result for this fixture. The artifact does **not** survive its broader fail-closed claim: malformed-but-parseable ID types crash with uncaught `TypeError`; `shape_only` accepts them. More importantly, source duplicate IDs are silently last-write-wins, missing source fields can make report `null` pass, `check()` trusts expected IDs but not expected values, and `budget_exports` is ignored even though the task freezes it at 3 while the expected report has 4 items. Those are real trust and robustness holes, but they require changed inputs or a caller that relies on the unused budget field; none yielded an accepted wrong report under the immutable published fixture.
