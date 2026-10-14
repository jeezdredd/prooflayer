import { Link } from "react-router-dom";
import LegalLayout from "../components/LegalLayout";
import PrivacyRu from "./legal/PrivacyRu";
import { currentLang } from "../i18n";
import { LEGAL, operatorLine } from "../legal";

const h2 = "text-ink-100 text-base mb-3";
const list = "list-disc list-inside space-y-1 text-ink-400";
const link = "text-iris hover:underline";
const label = "text-ink-300";

function Mail({ to }: { to: string }) {
  return <a href={`mailto:${to}`} className={link}>{to}</a>;
}

export default function PrivacyPage() {
  if (currentLang() === "ru") return <PrivacyRu />;
  return (
    <LegalLayout title="Privacy Policy" updated={LEGAL.updated}>
      <section>
        <h2 className={h2}>1. Who we are</h2>
        <p>{LEGAL.brand} is operated by {operatorLine()} ("we", "us"). This policy explains what personal data we process when you use {LEGAL.brand}, including the classroom service at classroom.prooflayer.cloud, why we process it, who receives it and what rights you have.</p>
        <p className="mt-2">For privacy questions and requests, write to <Mail to={LEGAL.emails.legal} />. For general help, write to <Mail to={LEGAL.emails.support} />. We answer requests within 30 days.</p>
      </section>

      <section>
        <h2 className={h2}>2. What we collect</h2>
        <ul className={list}>
          <li><strong className={label}>Account:</strong> email address, username, password (stored only as a hash), optional avatar and bio, whether your email is verified, and whether and when you agreed to help improve detection.</li>
          <li><strong className={label}>Uploads:</strong> the files you submit (images, video, audio, text, PDF, DOCX) and their file names, text extracted from documents, file metadata (EXIF, XMP, C2PA), file hashes, perceptual hashes, image embeddings, and the analysis results and verdicts.</li>
          <li><strong className={label}>Classroom:</strong> schools (name and address slug), memberships and roles, class names and year (school grade or university year), and work handed in to classes.</li>
          <li><strong className={label}>Billing:</strong> your plan, subscription status and Paddle customer and subscription identifiers. We never see or store card numbers.</li>
          <li><strong className={label}>API:</strong> API key name, prefix and a SHA-256 hash of the key (the key itself is shown to you once), and an optional webhook URL and secret that you set.</li>
          <li><strong className={label}>Public results and community:</strong> results you choose to make public, and votes and reports you file on public results.</li>
          <li><strong className={label}>Fact Check:</strong> the text, document or web address you submit to the Fact Check tool. It is not saved to your history and is kept only temporarily to show you the result.</li>
          <li><strong className={label}>Feedback and messages:</strong> feedback you send through the feedback form, with the optional contact email you give, and emails you send us.</li>
          <li><strong className={label}>Technical:</strong> IP address, approximate country and city and network provider derived from it, browser details, the page you arrived on and the referring page, access logs and error logs.</li>
          <li><strong className={label}>Cookies and browser storage:</strong> see section 12.</li>
        </ul>
      </section>

      <section>
        <h2 className={h2}>3. Why we use it and on what basis</h2>
        <ul className={list}>
          <li><strong className={label}>To provide the service you asked for</strong> (performing our contract with you): creating and securing your account, analysing uploads, running originality checks, running classes, providing the API and sending emails such as verification and billing messages.</li>
          <li><strong className={label}>To handle payments</strong> (contract and legal obligations): through Paddle, our merchant of record.</li>
          <li><strong className={label}>To keep the service safe and working</strong> (our legitimate interest): preventing abuse and fraud, enforcing usage limits, monitoring operations and fixing errors.</li>
          <li><strong className={label}>To show a result publicly</strong> (your choice): only if you make that result public, as described in section 5.</li>
          <li><strong className={label}>To improve our detectors</strong> (your consent): only if you opt in, as described in section 7.</li>
          <li><strong className={label}>Class work</strong> is processed on behalf of the school or university, as described in section 8.</li>
        </ul>
        <p className="mt-2">We do not sell personal data and we do not use it for advertising.</p>
      </section>

      <section>
        <h2 className={h2}>4. Where your data is stored and processed</h2>
        <p>Our application servers, database and file storage are self-hosted in the {LEGAL.country}, in line with the Kazakhstan requirement to store personal data on servers located in Kazakhstan.</p>
        <p className="mt-2">All AI analysis runs on our own servers. This includes the image, video, audio and text detectors, the vision and text language models and the text embeddings. Your uploads are not sent to OpenAI, Anthropic, Google or any other external AI provider for analysis. Short search queries taken from texts do go to web search engines and Wikipedia, as described in section 5.</p>
      </section>

      <section>
        <h2 className={h2}>5. Who receives your data</h2>
        <p>We share personal data only with the following recipients, and only what each one needs:</p>
        <ul className={`${list} mt-2`}>
          <li><strong className={label}>Cloudflare, Inc. (USA):</strong> DNS, content delivery, secure tunnel and DDoS protection. HTTPS connections end at Cloudflare's network, so all traffic to and from {LEGAL.brand}, including your uploads, passes through Cloudflare in transit.</li>
          <li><strong className={label}>Paddle.com Market Ltd (UK):</strong> merchant of record for paid plans. Paddle collects your payment details, handles taxes and issues invoices. Paddle's own buyer terms and privacy notice apply to the purchase.</li>
          <li><strong className={label}>Resend (email delivery on Amazon SES, Ireland):</strong> receives your email address and the content of transactional emails, such as verification and billing messages.</li>
          <li><strong className={label}>Apple iCloud Mail:</strong> hosts our support and legal mailboxes, so it holds the emails you send us.</li>
          <li><strong className={label}>ip-api.com:</strong> receives visitors' IP addresses so we can derive an approximate country, city and network provider for operations monitoring.</li>
          <li><strong className={label}>Discord, Inc. (USA):</strong> if our internal team notifications are enabled, our private team channel on Discord receives visit notices (IP address, approximate location and network provider, the page you arrived on, the referring page and browser) and the feedback you send through the feedback form, together with your account email and the contact email you give.</li>
          <li><strong className={label}>Web search engines (Google, Bing, DuckDuckGo, Yandex and Brave):</strong> for the originality check of a text, up to 8 distinctive sentences of at most 14 words each are sent as search queries through our self-hosted search gateway. If the gateway is unavailable, the queries go directly to the Brave Search API, where enabled, or to DuckDuckGo. Pages found are then downloaded from the open web for comparison.</li>
          <li><strong className={label}>DuckDuckGo and Wikipedia (Wikimedia Foundation):</strong> if you use the Fact Check tool, a search query of up to 200 characters made from your text is sent to DuckDuckGo, and up to 4 short claims of at most 120 characters each are looked up on Wikipedia.</li>
          <li><strong className={label}>Anyone on the internet:</strong> only if you choose to make a result public. A public result shows your username, the date you joined, the file name, a preview image and the analysis results. You can make it private again at any time. Work handed in to a class cannot be made public.</li>
          <li><strong className={label}>Sentry:</strong> if error monitoring is enabled, Sentry may receive technical error reports.</li>
          <li><strong className={label}>Your school or university:</strong> if you hand in work to a class, see section 8.</li>
        </ul>
        <p className="mt-2">Some of these recipients are outside Kazakhstan, so the data they receive is transferred abroad for the purposes described above. We may also disclose data where the law requires it.</p>
      </section>

      <section>
        <h2 className={h2}>6. Originality checks and the repository</h2>
        <ul className={list}>
          <li>Every text, PDF or DOCX submission is compared with the {LEGAL.brand} repository and with the web.</li>
          <li>Work handed in to a class is stored in the repository and compared with future submissions from any school or university and with personal uploads by any {LEGAL.brand} user.</li>
          <li>When a match comes from a submission you may not open, such as work from another institution or from another class of the same school, the report shows it only as "Another ProofLayer submission" with its submission date and the matching passages of your own text. The other work's text, author and file name are never shown.</li>
          <li>Personal uploads are compared with the repository but are not added to it.</li>
        </ul>
      </section>

      <section>
        <h2 className={h2}>7. Model training (opt-in)</h2>
        <ul className={list}>
          <li>Helping improve detection is optional and off by default. You can turn it on at registration or on your <Link to="/account" className={link}>account page</Link> ("Help improve detection").</li>
          <li>If you opt in, only personal uploads that our reviewers have labelled as real or AI are copied into a separate training set. The copy holds no account details, only a keyed pseudonym that lets us honour a withdrawal.</li>
          <li>You can withdraw at any time on your account page. Withdrawing deletes those copies. Detectors already trained with them are not retrained.</li>
          <li>Deleting a single upload does not delete its training copy. Withdrawing consent does.</li>
          <li>If you delete your account, the training copies are kept unless you tick "also delete the anonymous training copies".</li>
          <li>Class work, and anything a student hands in to a class, is never used for training.</li>
          <li>Most of our training data comes from public research datasets.</li>
        </ul>
      </section>

      <section>
        <h2 className={h2}>8. Schools, students and children</h2>
        <ul className={list}>
          <li>For work handed in to a class, the school or university decides why and how student data is processed (it is the controller). We process that data on its behalf (as processor) under our <Link to="/data-processing" className={link}>Data Processing terms</Link>.</li>
          <li>The institution is responsible for having a lawful basis and, where students are minors, for obtaining the consent of their parents or legal representatives.</li>
          <li>Teachers see only work handed in to their own classes, never a student's personal uploads. School admins see all classes of their school. Teachers of the same school do not see each other's classes.</li>
          <li>Anyone may open an account. We record whether you said you are 18 or older and when you said it, and use it only to decide access to sensitive public material and publishing. Users under 18 should use ProofLayer with the permission of a parent or legal representative.</li>
          <li>Students and parents with questions about class work should contact the school first. We will help the school answer.</li>
        </ul>
      </section>

      <section>
        <h2 className={h2}>9. Automated results</h2>
        <p>Our AI verdicts, originality matches and text signals (such as hidden bypass characters, vocabulary compared with the class year, and style compared with a student's earlier work) are probabilistic. They are a reason to talk to the student, never proof. Most results are produced automatically; only some cases, such as split or escalated results, are reviewed by our staff. Our staff reviewers can open those submissions, including class work, see the sources of their originality matches and change the verdict. Institutions must not base disciplinary or grading decisions solely on {LEGAL.brand} output and must give the student a chance to respond.</p>
      </section>

      <section>
        <h2 className={h2}>10. How long we keep data</h2>
        <ul className={list}>
          <li><strong className={label}>Personal uploads</strong> (not handed in to a class): the file and its preview image are deleted from storage 90 days after upload by a daily job, together with the stored text used for its originality report. The file name, extracted metadata, hashes, image embedding, verdict, scores and result history stay until you delete the upload or your account.</li>
          <li><strong className={label}>Single uploads:</strong> you can delete any upload at any time, which deletes the file and its results. A training copy, if one was made, is handled as described in section 7.</li>
          <li><strong className={label}>Class work:</strong> kept until the school deletes the school, or until the student deletes that work or their account. If a teacher deletes their account, classes inside a school pass to the school owner and their work stays with the school, while classes outside any school are deleted together with all work handed in to them.</li>
          <li><strong className={label}>Account data:</strong> kept until you delete your account.</li>
          <li><strong className={label}>Email logs and feedback:</strong> our record of emails we sent you (your email address, the type of email and whether it was delivered) and feedback you sent us are kept until you delete your account.</li>
          <li><strong className={label}>Training copies:</strong> kept until you withdraw consent or ask for them to be deleted with your account (section 7).</li>
          <li><strong className={label}>Backups:</strong> database backups are kept for 14 days, so deleted data can remain in backups for up to 14 days.</li>
        </ul>
        <p className="mt-2">When a school owner deletes a school, all its classes and all work handed in to them are deleted.</p>
      </section>

      <section>
        <h2 className={h2}>11. Your rights and how to use them</h2>
        <p>Under the Law of the Republic of Kazakhstan "On Personal Data and Their Protection" you can ask to know what data we hold about you, get access to it, have it corrected, completed or deleted, and withdraw your consent. If you are in the EU or UK, you also have the rights to access, rectification, erasure, restriction of processing, data portability and objection, and you can complain to your data protection supervisory authority.</p>
        <ul className={`${list} mt-2`}>
          <li><strong className={label}>Delete your account yourself</strong> on the <Link to="/account" className={link}>account page</Link>, confirmed with your password. This deletes your account, all your uploads and results, API keys, class memberships, the work you handed in to classes, your feedback messages and our record of emails sent to you. Classes you teach are handled as described in section 10. If you own a school, you must delete the school first. If you have an active paid subscription, cancel it in the billing portal first; free accounts are deleted immediately.</li>
          <li><strong className={label}>Withdraw training consent</strong> on the account page at any time.</li>
          <li><strong className={label}>Access, correction, export and other requests:</strong> write to <Mail to={LEGAL.emails.legal} /> from the email address on your account. We answer within 30 days.</li>
        </ul>
      </section>

      <section>
        <h2 className={h2}>12. Cookies and browser storage</h2>
        <ul className={list}>
          <li>We set one strictly necessary cookie, <code className={label}>prooflayer_refresh</code>, on our API host. It keeps you signed in, including on classroom.prooflayer.cloud, and is httpOnly, Secure and SameSite=Lax.</li>
          <li>Your browser keeps your access token in sessionStorage and your profile in localStorage, together with small flags such as whether you closed the cookie notice, whether this visit was already counted and which language you chose.</li>
          <li>We do not use analytics or advertising cookies.</li>
        </ul>
      </section>

      <section>
        <h2 className={h2}>13. Security</h2>
        <ul className={list}>
          <li>HTTPS on every connection between your browser and {LEGAL.brand}.</li>
          <li>Passwords hashed with PBKDF2; API keys stored only as SHA-256 hashes.</li>
          <li>Webhooks signed with HMAC-SHA256.</li>
          <li>Uploaded files kept in private storage and served only through short-lived signed links.</li>
          <li>Access to production systems limited to the operator.</li>
          <li>If a security incident affects personal data, we notify affected institutions without undue delay, and within 72 hours of becoming aware for customers under our Data Processing terms.</li>
        </ul>
      </section>

      <section>
        <h2 className={h2}>14. Changes to this policy</h2>
        <p>We may update this policy when the service or the law changes. The current version is always on this page with its "Last updated" date. Where the law requires us to notify you or ask for your consent, we will do so.</p>
      </section>

      <section>
        <h2 className={h2}>15. Contact</h2>
        <p>Operator: {operatorLine()}. Privacy and data requests: <Mail to={LEGAL.emails.legal} />. Support: <Mail to={LEGAL.emails.support} />.</p>
      </section>
    </LegalLayout>
  );
}
