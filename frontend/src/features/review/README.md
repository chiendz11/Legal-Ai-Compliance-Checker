Reviewer workbench (C12), the "Rà soát" tab of a report.

- `GET .../review-state` lists every reviewable machine finding with the hash the next review
  must quote; a 409 `STALE_REVIEW` means someone else reviewed it first, and the state reloads.
- Decisions: Xác nhận, Chỉnh sửa (OVERRIDE of the editable fields only), Yêu cầu bổ sung, Bác bỏ,
  Ghi chú. A reason is required. Machine output is never edited; overrides are a layer on top.
- New reviews need a rebuilt report version (`POST .../reports`) before publishing
  (`POST /reports/{id}/publish`, publisher role). The server decides what blocks publication.
- History of the run is shown in the Audit tab.
