# Consumer: notifications-service

Reads the customer report line and parses `<N> orders` into the SMS "You have N active orders".

- Owner: CX team, `#notifications` in Slack.
- Contract: `N` = non-cancelled orders of the customer. Agreed after INC-231, when cancelled orders
  were counted and customers received SMS with too-high numbers.
- The service has no own filter — it trusts the report. Changing what `N` counts is a contract change
  and needs the CX team's sign-off.
