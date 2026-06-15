export default function RefundPage() {
  return (
    <div className="max-w-3xl mx-auto py-16 px-6">
      <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-ink-600 mb-3">Legal</div>
      <h1 className="font-display text-3xl text-ink-50 mb-2">Refund Policy</h1>
      <p className="font-mono text-[10px] text-ink-500 mb-10">Last updated: June 15, 2025</p>

      <div className="prose prose-invert prose-sm max-w-none space-y-8 font-mono text-[13px] text-ink-300 leading-relaxed">
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
          <p>Email <a href="mailto:hello@prooflayer.com" className="text-iris hover:underline">hello@prooflayer.com</a> with your account email and reason. We process refunds within 5 business days.</p>
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
          <p><a href="mailto:hello@prooflayer.com" className="text-iris hover:underline">hello@prooflayer.com</a></p>
        </section>
      </div>
    </div>
  );
}
