# Recurring subscription scope

**Status:** AWAITING MOHIT SIGNOFF  
**Rollout:** default-off; Razorpay test mode → staging → explicitly selected cohort → production

## 0. Existing surfaces audit

### Existing surfaces

- `frontend/src/pages/Pricing.jsx` renders Free and Pro, creates a Razorpay order, verifies a successful payment and labels the result as a monthly subscription.
- `backend/routes/billing.py` securely verifies an order-payment HMAC and then writes `users.plan = "pro"`. It has no subscription, renewal, cancellation, expiry, grace or failed-payment lifecycle.
- `backend/subscription_service.py` owns plan limits and effective entitlement. Dev mode and admin/reviewer access are explicit non-payment bypasses.
- `frontend/src/pages/TermsOfService.jsx` promises recurring charges until cancellation.
- `frontend/src/pages/RefundPolicy.jsx` promises cancellation at period end, payment retries and downgrade after repeated failure.
- `frontend/src/pages/Settings.jsx` has no subscription-management surface.
- The insecure mock `POST /subscription/upgrade` and its direct mutation helper were removed before this scope because they were an existing security defect, not part of the new feature.

### Overlap and differentiation

The existing checkout is a legitimate one-time-payment flow, but its customer-facing language describes a recurring product that does not exist. This scope does not create a second billing system. It replaces the one-time entitlement mutation with a provider-backed subscription lifecycle and extends Pricing plus Settings to show truthful state.

### Decision

**REPLACE the existing one-time “monthly” entitlement behavior; EXTEND the existing Pricing and Settings surfaces.** There will be one entitlement reader and one Razorpay subscription lifecycle. No parallel credits, lifetime plan or second payment provider is introduced in V1.

## 1. What it is

ChessGuru Pro becomes a real recurring subscription. A successful provider event activates Pro for a defined paid period. Renewal extends that period; cancellation stops future renewal while preserving access to the paid-through date; failed payment enters an explicit provider-backed state; expiry returns the user to Free. The browser never grants entitlement. The database records provider facts and derives access from them.

## 2. What the user sees

### Pricing — before subscribing

```text
ChessGuru Pro
₹[tested price] / month

Your coach keeps watching your games, carries your active plan across
Review and Coach Play, and checks whether the fix transfers.

[ Start Pro ]

Renews monthly until cancelled. Taxes are shown at checkout.
You can cancel from Settings. Access continues through the paid period.
```

### Settings — active

```text
Subscription

Pro · Active
Next renewal: 28 September 2026

[ Manage subscription ]   [ Cancel renewal ]
```

### Settings — cancelled, access remains

```text
Subscription

Pro · Cancels on 28 September 2026
You keep Pro access until that date. You will not be charged again.

[ Resume subscription ]
```

### Settings — payment problem

```text
Subscription

Payment needs attention
Razorpay could not renew your plan. Your access status and the date on
which it changes are shown below.

[ Update payment method ]
```

### Settings — expired

```text
Subscription

Free
Your Pro subscription ended on 28 September 2026.
Your games, focuses and progress history are still here.

[ Restart Pro ]
```

No screen says “payment succeeded” until the server has a verified provider event. No screen says “active,” “renews,” “cancelled” or “paid through” from client-held state.

## 3. In scope (V1)

- Razorpay recurring subscription creation for the selected monthly Pro package.
- Server-side correlation between ChessGuru user, provider customer, provider subscription and provider payment.
- Signed webhook verification using the raw request body.
- Idempotent processing of subscription authenticated, activated, charged, pending, halted, cancelled and completed/expired states required by the provider contract.
- One canonical subscription record with provider event history references and a separate immutable/idempotent event ledger.
- Effective entitlement derived from authoritative subscription state and paid-through time.
- Pricing checkout updated to create a subscription rather than a one-time order.
- Settings state for active, cancellation scheduled, payment problem and expired/free.
- Cancel-at-period-end and resume/reactivate behavior supported when the provider supports it.
- Admin/reviewer and local DEV_MODE access remain explicit, inspectable non-payment bypasses.
- Test-mode webhook replay, out-of-order delivery and duplicate-delivery coverage.
- Migration decision for the two current `plan=pro` users and three `created` payment intents before rollout.
- Terms, Refund Policy and checkout wording changed to match the implemented lifecycle exactly.
- Default-off environment flag and cohort rollout.

## 4. Explicitly out of scope (V1)

- Annual, lifetime, family, academy, team or gift plans.
- Multiple paid tiers.
- A second payment provider.
- Usage credits or consumable analysis packs.
- App Store or Google Play billing.
- Automatic currency conversion or geographically inferred price discrimination.
- Dunning behavior invented by ChessGuru when Razorpay already owns the retry state.
- Revenue recognition, tax filing or accounting automation beyond storing provider invoice/payment identifiers needed for support.
- Changing the coaching package or exact price; packaging and price are a separate data-locked experiment.
- Deleting a player's games, focuses or progress when a subscription expires.

## 5. Success criteria

- A normal authenticated user cannot receive Pro from any browser request without a verified provider subscription/payment event.
- Duplicate or out-of-order webhook delivery produces the same final entitlement as one correctly ordered delivery and never extends access twice.
- Every provider lifecycle state in the agreed event matrix produces the exact Settings state and access result shown in the product contract.
- Cancellation stops future renewal and preserves access only through the authoritative paid-through date.
- A failed or expired subscription cannot remain permanently Pro because of a stale `users.plan` field.
- A returning user can understand whether they will be charged again and when access changes without contacting support.
- Checkout-start, verified activation, cancellation, renewal failure, recovery and expiry events are observable without including card or sensitive payment data.
- Provider test-mode checkout → activation → cancellation → expiry is reproduced end to end before cohort rollout.

Commercial conversion targets are not a success criterion for the correctness scope. They are set and measured in the later packaging experiment after the lifecycle is safe.

## 6. Open questions

- **Question:** What monthly India price and global package should V1 use?  
  **Why unresolved:** The current ₹149 default is not supported by ARR economics, while willingness-to-pay has not been measured.  
  **Unblocking step:** Run the pre-registered packaging experiment from the master action plan; lock the winning cell from paid conversion, refunds and early retention.

- **Question:** What exact retry/grace behavior does the selected Razorpay configuration guarantee?  
  **Why unresolved:** The policy currently claims three retries over seven days, but code and provider configuration have not been reconciled.  
  **Unblocking step:** Record the provider's configured event/state matrix and have policy/legal review approve the resulting customer copy.

- **Question:** Can cancellation and payment-method updates be completed through a provider-hosted management surface, or must ChessGuru call provider APIs?  
  **Why unresolved:** Current account configuration has not been inspected in this scope.  
  **Unblocking step:** Verify capabilities in Razorpay test mode and select the smallest secure flow.

- **Question:** How should the two existing Pro-marked users be classified?  
  **Why unresolved:** Production has no successful payment intent supporting those entitlements; they may be admin/test access.  
  **Unblocking step:** Inspect only their role and entitlement provenance with Mohit's approval, then migrate to explicit admin/reviewer access or a dated complimentary grant.

- **Question:** Is a GST invoice generated and delivered by Razorpay for this configuration?  
  **Why unresolved:** Checkout currently stores only order/payment identifiers.  
  **Unblocking step:** Verify provider invoicing configuration with the business accountant before production charges.

## 7. Pre-code requirements

- Mohit explicitly signs off this entire scope.
- Razorpay test-mode account supports the required recurring subscription and management capabilities.
- Test plan/product identifiers and webhook secret are available through environment variables; none is committed.
- The provider event/state matrix, signature procedure and raw-body requirement are copied from current official Razorpay documentation and reviewed.
- Exact entitlement state machine and paid-through semantics are written before schema or handlers.
- Existing `payment_intents`, `users.plan` readers and every feature gate are inventoried so no stale bypass remains.
- Migration treatment for two Pro-marked users and three created intents is approved.
- Pricing and policy text for every lifecycle state is approved.
- Packaging price remains configurable and is not gut-locked in implementation.
- Unit, integration, webhook replay, security and staging E2E cases are enumerated before the first lifecycle code change.

