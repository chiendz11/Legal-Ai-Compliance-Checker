# Frontend API client

`client.ts` dùng openapi-fetch và types trong `schema.d.ts` được sinh từ
`docs/architecture/openapi.design.json`. `npm run gen:api` cập nhật types; CI kiểm diff.
Queries/mutations ở `queries.ts`; tenant/actor/permission do backend xác định.

26 operations đã có handler. Mock là lựa chọn phát triển rõ ràng, không phải output
inference thật. Contract nghiệp vụ/status nằm ở docs/contracts/integration_spec.md;
không tự kết luận UNKNOWN là vi phạm hoặc VERIFY_REFERENCE là hành động khắc phục.
