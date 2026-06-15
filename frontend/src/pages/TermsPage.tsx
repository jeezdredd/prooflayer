export default function TermsPage() {
  return (
    <div className="max-w-3xl mx-auto py-16 px-6">
      <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-ink-600 mb-3">Legal</div>
      <h1 className="font-display text-3xl text-ink-50 mb-2">Terms of Service</h1>
      <p className="font-mono text-[10px] text-ink-500 mb-10">Last updated: June 15, 2025</p>

      <div className="prose prose-invert prose-sm max-w-none space-y-8 font-mono text-[13px] text-ink-300 leading-relaxed">
        <section>
          <h2 className="text-ink-100 text-base mb-3">1. Acceptance of Terms</h2>
          <p>By accessing or using ProofLayer ("Service"), you agree to be bound by these Terms of Service. If you do not agree, do not use the Service.</p>
        </section>

        <section>
          <h2 className="text-ink-100 text-base mb-3">2. Description of Service</h2>
          <p>ProofLayer is an AI-generated content detection platform. Users upload images, videos, audio, and text files for authenticity analysis using machine learning models. Results are provided as probability scores and verdicts and should not be treated as definitive legal evidence.</p>
        </section>

        <section>
          <h2 className="text-ink-100 text-base mb-3">3. User Accounts</h2>
          <p>You must provide accurate information when creating an account. You are responsible for maintaining the security of your credentials. One account per person.</p>
        </section>

        <section>
          <h2 className="text-ink-100 text-base mb-3">4. Acceptable Use</h2>
          <p>You may not use the Service to:</p>
          <ul className="list-disc list-inside space-y-1 mt-2 text-ink-400">
            <li>Upload illegal, harmful, or abusive content</li>
            <li>Attempt to reverse-engineer or exploit the detection models</li>
            <li>Circumvent usage limits or access controls</li>
            <li>Resell or redistribute the Service without written permission</li>
          </ul>
        </section>

        <section>
          <h2 className="text-ink-100 text-base mb-3">5. Subscriptions and Payment</h2>
          <p>Paid plans are billed monthly via Paddle. Charges are non-refundable except as described in our Refund Policy. You may cancel at any time; access continues until the end of the billing period.</p>
        </section>

        <section>
          <h2 className="text-ink-100 text-base mb-3">6. Intellectual Property</h2>
          <p>You retain ownership of content you upload. By uploading, you grant ProofLayer a limited license to process that content for analysis purposes only. ProofLayer retains all rights to its platform, models, and software.</p>
        </section>

        <section>
          <h2 className="text-ink-100 text-base mb-3">7. Limitation of Liability</h2>
          <p>The Service is provided "as is." ProofLayer makes no guarantees of accuracy. We are not liable for decisions made based on analysis results. Our total liability is limited to the amount paid in the 12 months preceding any claim.</p>
        </section>

        <section>
          <h2 className="text-ink-100 text-base mb-3">8. Termination</h2>
          <p>We may suspend or terminate accounts that violate these Terms. You may delete your account at any time from account settings.</p>
        </section>

        <section>
          <h2 className="text-ink-100 text-base mb-3">9. Changes to Terms</h2>
          <p>We may update these Terms at any time. Continued use of the Service after changes constitutes acceptance.</p>
        </section>

        <section>
          <h2 className="text-ink-100 text-base mb-3">10. Contact</h2>
          <p>Questions: <a href="mailto:hello@prooflayer.com" className="text-iris hover:underline">hello@prooflayer.com</a></p>
        </section>
      </div>
    </div>
  );
}
