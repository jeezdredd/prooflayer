import { Link } from "react-router-dom";
import LegalLayout from "../components/LegalLayout";
import { LEGAL, operatorLine } from "../legal";

const linkClass = "text-iris hover:underline";

export default function RefundPage() {
  return (
    <LegalLayout title="Refund Policy" updated={LEGAL.updated}>
      <section>
        <h2 className="text-ink-100 text-base mb-3">1. Who handles payments and refunds</h2>
        <p>
          {LEGAL.brand} is provided by {operatorLine()}. Paid plans are sold through Paddle.com Market Ltd (UK), which acts
          as the merchant of record. Paddle processes your payment, adds taxes where required and issues invoices. We never
          see your card number. Paddle's buyer terms also apply to your purchase.
        </p>
        <p className="mt-3">
          Refunds are issued by Paddle to the original payment method used for the purchase.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">2. 14-day money-back period</h2>
        <p>
          If you start a new subscription to Pro, School or University online through the checkout on the{" "}
          <Link to="/pricing" className={linkClass}>Pricing page</Link>, you can ask for a full refund of the first payment
          of that subscription within 14 days of that payment. This applies to both monthly and yearly billing. You do not
          have to give a reason.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">3. Renewals and partial periods</h2>
        <p>
          Subscriptions renew automatically until you cancel them. Renewal payments, and any unused part of a billing
          period after the first 14 days, are not refunded, except where the law requires a refund.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">4. Cancelling</h2>
        <ul className="list-disc list-inside space-y-1 text-ink-400">
          <li>
            You can cancel at any time in the billing portal (<Link to="/pricing" className={linkClass}>Pricing page</Link>,
            "Manage").
          </li>
          <li>After you cancel, you keep access to your paid plan until the end of the period you have already paid for.</li>
          <li>After that period ends, the subscription does not renew and you are not charged again.</li>
          <li>
            Asking for a refund does not by itself cancel your subscription, and cancelling does not by itself refund a
            payment. If you want both, cancel in the billing portal and write to us as described in section 7.
          </li>
          <li>
            You cannot delete your {LEGAL.brand} account while a paid subscription is active. Cancel it in the billing
            portal first, so you are not charged again. Deleting your account does not by itself refund a payment.
          </li>
        </ul>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">5. Changing plans</h2>
        <p>
          Moving from a paid plan to Free is a cancellation and follows section 4. A change between paid plans, or between
          monthly and yearly billing, on an existing subscription is not a new subscription, so it does not start a new
          14-day money-back period. For questions about a plan change, write to{" "}
          <a href={`mailto:${LEGAL.emails.finance}`} className={linkClass}>{LEGAL.emails.finance}</a>.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">6. Enterprise and contract customers</h2>
        <p>
          If your organisation pays under a signed agreement or an Enterprise contract, refunds follow the terms of that
          agreement instead of this policy.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">7. How to ask for a refund</h2>
        <p>
          Email <a href={`mailto:${LEGAL.emails.finance}`} className={linkClass}>{LEGAL.emails.finance}</a> and include:
        </p>
        <ul className="list-disc list-inside space-y-1 mt-2 text-ink-400">
          <li>the email address of your {LEGAL.brand} account</li>
          <li>your plan and billing period (monthly or yearly)</li>
          <li>the Paddle order or invoice number, if you have it</li>
        </ul>
        <p className="mt-3">
          We answer refund requests within 30 days. Once Paddle issues a refund, the time it takes to reach your account
          depends on your bank or card provider.
        </p>
        <p className="mt-3">
          Our <Link to="/privacy" className={linkClass}>Privacy Policy</Link> explains how we handle the personal data in
          your request.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">8. Your statutory rights</h2>
        <p>
          Nothing in this policy limits rights you have under the consumer law of your country. If you are a consumer in
          the European Union or the United Kingdom, your statutory right of withdrawal is not limited by this policy.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">9. Contact</h2>
        <ul className="list-disc list-inside space-y-1 text-ink-400">
          <li>
            Refunds and invoices:{" "}
            <a href={`mailto:${LEGAL.emails.finance}`} className={linkClass}>{LEGAL.emails.finance}</a>
          </li>
          <li>
            Enterprise and contracts:{" "}
            <a href={`mailto:${LEGAL.emails.sales}`} className={linkClass}>{LEGAL.emails.sales}</a>
          </li>
          <li>
            Other questions:{" "}
            <a href={`mailto:${LEGAL.emails.support}`} className={linkClass}>{LEGAL.emails.support}</a>
          </li>
        </ul>
      </section>
    </LegalLayout>
  );
}
