import { Link } from "react-router-dom";
import LegalLayout from "../components/LegalLayout";
import { LEGAL, operatorLine } from "../legal";

export default function TermsPage() {
  return (
    <LegalLayout title="Terms of Service" updated={LEGAL.updated}>
      <section>
        <h2 className="text-ink-100 text-base mb-3">1. Agreement and who you contract with</h2>
        <p>
          These Terms of Service ("Terms") are an agreement between you and {operatorLine()} ("{LEGAL.brand}", "we", "us"). They apply to the {LEGAL.brand} website, the classroom at classroom.prooflayer.cloud, the API and every other part of the service (the "Service").
        </p>
        <p className="mt-3">
          By creating an account, joining a class, or using the Service or the API, you accept these Terms. If you do not accept them, do not use the Service. If you use the Service for a school, university, company or other organisation, you confirm that you are allowed to accept these Terms for it, and "you" then also means that organisation.
        </p>
        <p className="mt-3">
          Our <Link to="/privacy" className="text-iris hover:underline">Privacy Policy</Link> explains how we handle personal data. For work handed in to a class, our <Link to="/data-processing" className="text-iris hover:underline">Data Processing terms</Link> also apply between us and the institution.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">2. Eligibility and age</h2>
        <ul className="list-disc list-inside space-y-1 text-ink-400">
          <li>Anyone may create an account. You tell us whether you are 18 or older; you can change this on your account page.</li>
          <li>If you are under 18, use the Service with the permission of a parent or legal representative.</li>
          <li>Other people's public uploads may include adult material. Uploads marked as sensitive are shown only to signed-in users who said they are 18 or older, and only users who said they are 18 or older can publish their own uploads to the public feed. If you change your answer to under 18, your public uploads are taken off the feed.</li>
          <li>Telling us a false age is a breach of these Terms.</li>
          <li>You must not use the Service if the law of your country does not allow you to.</li>
        </ul>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">3. Accounts, security and API keys</h2>
        <ul className="list-disc list-inside space-y-1 text-ink-400">
          <li>Give accurate information when you register and keep your email address up to date.</li>
          <li>Keep your password secret. You are responsible for everything done through your account.</li>
          <li>Tell us at <a href={`mailto:${LEGAL.emails.support}`} className="text-iris hover:underline">{LEGAL.emails.support}</a> without delay if you believe someone else has accessed your account.</li>
          <li>An API key is shown only once when you create it. We store only a hash of it, so we cannot show it to you again.</li>
          <li>Keep API keys and webhook secrets private. Do not put them in public code, web pages or apps. Revoke a key straight away if it may have leaked.</li>
          <li>You are responsible for all requests made with your API keys, including the usage they count against your plan.</li>
        </ul>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">4. The Service and its limits</h2>
        <p>
          {LEGAL.brand} analyses images, video, audio, text and documents for signs of AI generation or manipulation, and checks texts for originality against the {LEGAL.brand} repository and the web.
        </p>
        <ul className="list-disc list-inside space-y-1 mt-3 text-ink-400">
          <li>Results, scores, verdicts and text signals are probabilistic estimates. They can be wrong in both directions: genuine work can be flagged, and AI-generated or copied work can be missed.</li>
          <li>We do not guarantee that any result is accurate, complete or suitable for a particular purpose.</li>
          <li>Results are not legal evidence and are not proof of misconduct, cheating, plagiarism or AI use. They are a reason to look closer and to talk to the person concerned.</li>
          <li>Not every result is checked by a person. Most results are produced automatically, and only some cases, such as split or escalated results, are reviewed by our staff.</li>
          <li>You decide how to use results and you are responsible for the decisions you make.</li>
          <li>We may change, add or remove features over time.</li>
        </ul>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">5. Use in schools and universities</h2>
        <p>
          A school or university that uses the classroom (the "institution") decides why and how student work is processed. For that work the institution is the data controller and we process it on its behalf under the <Link to="/data-processing" className="text-iris hover:underline">Data Processing terms</Link>. The institution agrees that:
        </p>
        <ul className="list-disc list-inside space-y-1 mt-3 text-ink-400">
          <li>it has a lawful basis for processing its students' work and personal data through the Service, and tells students, and parents where relevant, how the Service is used;</li>
          <li>where students are minors, it obtains the consent of parents or legal representatives where the law requires it;</li>
          <li>it controls who receives its teacher and class codes, and who acts as a teacher or school administrator;</li>
          <li>it will not base any disciplinary decision, grade or other decision about a student solely on {LEGAL.brand} output;</li>
          <li>before any such decision, the student will have a fair chance to see the concern and respond to it.</li>
        </ul>
        <p className="mt-3">
          Teachers see only work handed in to their own classes. They never see a student's personal uploads, and teachers of the same school do not see each other's classes. School administrators see all classes of their school. Our staff reviewers can open split or escalated submissions, including class work, to review the result. Work handed in to a class cannot be made public.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">6. Originality repository</h2>
        <p>
          Every text, PDF or DOCX submission is compared with the {LEGAL.brand} repository and with pages on the web. To search the web, up to 8 distinctive sentences from the text, each cut to at most 14 words, are sent as search queries to web search engines, and pages found are downloaded from the open web for comparison, as described in the <Link to="/privacy" className="text-iris hover:underline">Privacy Policy</Link>.
        </p>
        <ul className="list-disc list-inside space-y-1 mt-3 text-ink-400">
          <li>Work handed in to a class is stored in the repository and compared with later submissions from any institution that uses {LEGAL.brand}, and with later personal uploads by any {LEGAL.brand} user.</li>
          <li>If your class work matches a submission checked by someone who is not allowed to see your work, such as a teacher at another institution, their report shows the match only as "Another ProofLayer submission", with its submission date and the matching passages of their own text. They do not see the text of your work, your name or the file name. This also applies to other classes of the same school.</li>
          <li>Personal uploads are compared with the repository but are not added to it.</li>
          <li>Class work is removed from the repository when the student deletes that work or their account, when the school deletes its school on {LEGAL.brand}, or when a teacher whose class is not part of a school deletes their account.</li>
        </ul>
        <p className="mt-3">
          By handing in work to a class, the student (and the institution, for its classes) gives us a non-exclusive, royalty-free licence to store that work in the repository and to use it only for comparison with other submissions, for as long as it is kept there.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">7. Acceptable use</h2>
        <p>You must not:</p>
        <ul className="list-disc list-inside space-y-1 mt-2 text-ink-400">
          <li>upload or process content that is illegal, including child sexual abuse material, or content you have no right to use;</li>
          <li>upload other people's personal data unless you have a lawful basis to do so;</li>
          <li>attack, overload or probe the Service, or try to access accounts, classes or data that are not yours;</li>
          <li>scrape the Service or collect data from it by automated means, except through the API as documented;</li>
          <li>get around usage limits, rate limits, plan restrictions or access controls, for example by creating several accounts;</li>
          <li>reverse engineer, decompile or try to extract our models, detectors or source code, except where the law expressly allows it;</li>
          <li>use results or other output of the Service to train, test or improve a competing detection product;</li>
          <li>resell, sublicense or provide the Service to others without our written permission;</li>
          <li>use the Service to harass, defame or discriminate against anyone.</li>
        </ul>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">8. Your content and our licence to use it</h2>
        <ul className="list-disc list-inside space-y-1 text-ink-400">
          <li>You keep all rights in the files and texts you upload.</li>
          <li>You give us a non-exclusive, royalty-free licence to store, copy and process your content only to provide the Service, including analysis, reports, the originality checks and, for class work, the originality repository described in section 6, and, only if you opt in, model training as described below.</li>
          <li>The Service is not a file storage service. The file of a personal upload (one not handed in to a class) is deleted 90 days after upload, together with the stored text used for its originality report. Its verdict, scores and result history stay until you delete them or your account. Keep your own copies of anything you need.</li>
          <li>You confirm that you have the rights and, where personal data is involved, the lawful basis needed to upload the content.</li>
          <li>We use your uploads to train our detectors only if you opt in by ticking "Help improve detection" at registration or on your <Link to="/account" className="text-iris hover:underline">account page</Link>. It is off by default. Only personal uploads that our reviewers have labelled as real or AI are copied into a separate training set, without your account details.</li>
          <li>You can withdraw that consent at any time on your account page, and the training copies are then deleted. Detectors already trained on them are not retrained. Deleting a single upload does not delete a training copy already made from it. If you delete your account instead, the training copies are kept unless you also tick "also delete the anonymous training copies".</li>
          <li>Work handed in to a class is never used for training.</li>
          <li>The Service, our software, models and reports remain ours. You may use the results and reports you receive for your own purposes, subject to these Terms.</li>
        </ul>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">9. Plans, billing and usage limits</h2>
        <ul className="list-disc list-inside space-y-1 text-ink-400">
          <li>Our plans, prices and limits are shown on the <Link to="/pricing" className="text-iris hover:underline">pricing page</Link>. The Free plan needs no card. Enterprise terms and prices are agreed in writing.</li>
          <li>Paid plans are sold by Paddle.com Market Ltd, which acts as merchant of record. Paddle processes the payment, adds taxes where required and issues invoices, and Paddle's buyer terms apply to the purchase. We never see your card number.</li>
          <li>Subscriptions, monthly or yearly, renew automatically at the end of each period until you cancel.</li>
          <li>You can cancel at any time in the billing portal. Your paid access continues until the end of the period you have already paid for.</li>
          <li>Each plan has usage limits, such as checks per month and API rate limits. When you reach a limit, further checks are refused until the limit resets or you upgrade.</li>
          <li>We may change prices. We will tell you in advance by email or in the Service, and a new price applies only from your next renewal after that notice. If you do not agree, you can cancel before the renewal.</li>
        </ul>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">10. Refunds</h2>
        <p>
          Refunds are covered by our <Link to="/refund" className="text-iris hover:underline">Refund Policy</Link>. Refund requests go to <a href={`mailto:${LEGAL.emails.finance}`} className="text-iris hover:underline">{LEGAL.emails.finance}</a>. Enterprise and other contract customers follow their agreement.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">11. Availability</h2>
        <p>
          We work to keep the Service running, but it may be unavailable at times because of maintenance, failures or problems with providers we rely on. We do not promise any level of uptime. A service level agreement applies only if an Enterprise contract states one.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">12. Suspension and termination</h2>
        <ul className="list-disc list-inside space-y-1 text-ink-400">
          <li>You can stop using the Service at any time and delete your account on your <Link to="/account" className="text-iris hover:underline">account page</Link>. A school owner must delete the school first.</li>
          <li>You cannot delete your account while a paid subscription is active. Cancel it in the billing portal first.</li>
          <li>If a teacher deletes their account, their classes in a school pass to the school owner together with the work handed in to them. Classes that are not part of a school are deleted together with all work handed in to them.</li>
          <li>We may suspend or close an account, an API key or a school if you break these Terms, if payment fails, if your use puts the Service or other users at risk, or if the law requires it. Where it is reasonable and allowed, we will usually tell you first.</li>
          <li>When an account or school is deleted, its data is deleted as described in the <Link to="/privacy" className="text-iris hover:underline">Privacy Policy</Link>, which also explains what is kept, such as training copies you chose to keep. Deleted data can remain in database backups for up to 14 days.</li>
          <li>Sections that by their nature should continue after termination, such as sections 13 to 16, continue to apply.</li>
        </ul>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">13. Disclaimers</h2>
        <p>
          To the extent the law allows, the Service is provided "as is" and "as available", without warranties of any kind, including warranties of accuracy, fitness for a particular purpose or uninterrupted operation. We are not responsible for decisions that you, an institution or anyone else make based on results from the Service.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">14. Limitation of liability</h2>
        <ul className="list-disc list-inside space-y-1 text-ink-400">
          <li>To the extent the law allows, we are not liable for indirect or consequential loss, lost profits, lost revenue, loss of data or damage to reputation.</li>
          <li>To the extent the law allows, our total liability for all claims relating to the Service is limited to the amount you paid for the Service in the 12 months before the event that caused the claim, or 100 USD if you used only free features.</li>
          <li>Nothing in these Terms excludes or limits liability that cannot be excluded or limited under the law that applies to you.</li>
        </ul>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">15. Indemnity</h2>
        <p>
          If you are an institution or use the API, you will compensate us for claims by third parties, and the reasonable costs of dealing with them, that arise from your breach of these Terms, from content you upload without the necessary rights or lawful basis, or from decisions you make using results in a way these Terms do not allow, such as relying on them alone for a disciplinary or grading decision. This section applies only to the extent the law allows.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">16. Governing law and disputes</h2>
        <p>
          These Terms are governed by the law of the {LEGAL.country}. Disputes will be heard by the courts at the operator's location. If you are a consumer, this does not take away the mandatory consumer protection rights you have under the law of your country of residence. Please contact us first, so we can try to resolve the issue without going to court.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">17. Changes to these Terms</h2>
        <p>
          We may update these Terms. The date at the top shows the latest version. For material changes we will tell you in advance by email or in the Service, before they take effect. If you keep using the Service after a change takes effect, the new Terms apply. If you do not agree, stop using the Service, cancel any paid subscription in the billing portal and, if you wish, delete your account.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">18. Contact</h2>
        <p>The Service is operated by {operatorLine()}.</p>
        <ul className="list-disc list-inside space-y-1 mt-3 text-ink-400">
          <li>Legal questions and these Terms: <a href={`mailto:${LEGAL.emails.legal}`} className="text-iris hover:underline">{LEGAL.emails.legal}</a></li>
          <li>Help with your account: <a href={`mailto:${LEGAL.emails.support}`} className="text-iris hover:underline">{LEGAL.emails.support}</a></li>
          <li>Refunds and invoices: <a href={`mailto:${LEGAL.emails.finance}`} className="text-iris hover:underline">{LEGAL.emails.finance}</a></li>
          <li>Schools, universities and Enterprise: <a href={`mailto:${LEGAL.emails.sales}`} className="text-iris hover:underline">{LEGAL.emails.sales}</a></li>
        </ul>
        <p className="mt-3">We answer requests within 30 days.</p>
      </section>
    </LegalLayout>
  );
}
