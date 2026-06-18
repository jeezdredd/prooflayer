import LegalLayout from "../components/LegalLayout";

export default function RefundPage() {
  return (
    <LegalLayout title="Refund Policy" updated="June 15, 2025">
      <section>
        <h2 className="text-ink-100 text-base mb-3">Subscription Refunds</h2>
        <p>
          We offer a <strong className="text-ink-100">7-day money-back guarantee</strong> for new Pro subscriptions. If you are not satisfied within the first 7 days of your first payment, contact us for a full refund.
        </p>
        <p className="mt-3">
          Renewals are non-refundable. You may cancel your subscription at any time - access continues until the end of the current billing period.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">How to Request a Refund</h2>
        <p>Email <a href="mailto:finance@prooflayer.cloud" className="text-iris hover:underline">finance@prooflayer.cloud</a> with your account email and reason. We process refunds within 5 business days.</p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">Exceptions</h2>
        <ul className="list-disc list-inside space-y-1 text-ink-400">
          <li>Accounts terminated for Terms of Service violations are not eligible for refunds</li>
          <li>Education and Enterprise plan refunds are governed by the individual agreement</li>
        </ul>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">Contact</h2>
        <p><a href="mailto:finance@prooflayer.cloud" className="text-iris hover:underline">finance@prooflayer.cloud</a></p>
      </section>
    </LegalLayout>
  );
}
