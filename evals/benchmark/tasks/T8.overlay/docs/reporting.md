# Customer report

`ReportService.BuildAsync(customerId)` renders one line: `<Title>: <N> orders at <timestamp>`.

`N` is the number of the customer's **non-cancelled** orders. Cancelled orders are never counted:
incident INC-231 (March 2026) was caused by counting them — customers with a cancelled order were
told they had more active orders than they did, and the notifications service sent the wrong SMS.
The fix shipped in 1.4.2 (see CHANGELOG.md) and the smoke test in CI pins the number for the seeded
customer 1 at `3 orders`.

Consumers: [notifications-service](consumers/notifications-service.md).
