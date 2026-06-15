export default function PrivacyPage() {
  return (
    <div className="max-w-3xl mx-auto py-16 px-6">
      <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-ink-600 mb-3">Legal</div>
      <h1 className="font-display text-3xl text-ink-50 mb-2">Privacy Policy</h1>
      <p className="font-mono text-[10px] text-ink-500 mb-10">Last updated: June 15, 2025</p>

      <div className="prose prose-invert prose-sm max-w-none space-y-8 font-mono text-[13px] text-ink-300 leading-relaxed">
        <section>
          <h2 className="text-ink-100 text-base mb-3">1. Information We Collect</h2>
          <ul className="list-disc list-inside space-y-1 text-ink-400">
            <li><strong className="text-ink-300">Account data:</strong> email address, username</li>
            <li><strong className="text-ink-300">Uploaded content:</strong> files submitted for analysis (images, video, audio, text)</li>
            <li><strong className="text-ink-300">Usage data:</strong> submission history, analysis results, timestamps</li>
            <li><strong className="text-ink-300">Payment data:</strong> handled entirely by Paddle - we do not store card numbers</li>
            <li><strong className="text-ink-300">Technical data:</strong> IP address, browser type, access logs</li>
          </ul>
        </section>

        <section>
          <h2 className="text-ink-100 text-base mb-3">2. How We Use Your Data</h2>
          <ul className="list-disc list-inside space-y-1 text-ink-400">
            <li>Provide and improve the detection service</li>
            <li>Retrain and improve our internal AI models (anonymized)</li>
            <li>Send transactional emails (account verification, billing)</li>
            <li>Prevent fraud and abuse</li>
          </ul>
        </section>

        <section>
          <h2 className="text-ink-100 text-base mb-3">3. Data Storage</h2>
          <p>Data is stored on servers in the European Union. Uploaded files are retained for 90 days after submission, then automatically deleted. You can delete your data at any time from your account settings.</p>
        </section>

        <section>
          <h2 className="text-ink-100 text-base mb-3">4. Third Parties</h2>
          <ul className="list-disc list-inside space-y-1 text-ink-400">
            <li><strong className="text-ink-300">Paddle:</strong> payment processing</li>
            <li><strong className="text-ink-300">Sentry:</strong> error monitoring (anonymized stack traces)</li>
            <li><strong className="text-ink-300">Cloudflare:</strong> CDN and DDoS protection</li>
          </ul>
          <p className="mt-2">We do not sell your data to third parties.</p>
        </section>

        <section>
          <h2 className="text-ink-100 text-base mb-3">5. Your Rights</h2>
          <p>You have the right to access, correct, or delete your personal data. Email <a href="mailto:hello@prooflayer.com" className="text-iris hover:underline">hello@prooflayer.com</a> to exercise these rights. We respond within 30 days.</p>
        </section>

        <section>
          <h2 className="text-ink-100 text-base mb-3">6. Cookies</h2>
          <p>We use only essential cookies required for authentication and session management. No advertising or tracking cookies.</p>
        </section>

        <section>
          <h2 className="text-ink-100 text-base mb-3">7. Contact</h2>
          <p><a href="mailto:hello@prooflayer.com" className="text-iris hover:underline">hello@prooflayer.com</a></p>
        </section>
      </div>
    </div>
  );
}
