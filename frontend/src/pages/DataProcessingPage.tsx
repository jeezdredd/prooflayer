import { Link } from "react-router-dom";
import LegalLayout from "../components/LegalLayout";
import DataProcessingRu from "./legal/DataProcessingRu";
import { currentLang } from "../i18n";
import { LEGAL, operatorLine } from "../legal";

const SUBPROCESSORS: { name: string; country?: string; purpose: string }[] = [
  {
    name: "Cloudflare, Inc.",
    country: "USA",
    purpose: "DNS, content delivery, secure tunnel and DDoS protection. HTTPS ends at Cloudflare's edge, so all traffic, including uploaded work, passes through Cloudflare in transit.",
  },
  {
    name: "Resend (on Amazon SES, region eu-west-1)",
    country: "Ireland",
    purpose: "Transactional email such as email verification and billing messages: recipients' email addresses and the content of those emails.",
  },
  {
    name: "Paddle.com Market Ltd",
    country: "United Kingdom",
    purpose: "Merchant of record for paid plans: payment data, taxes and invoices. We never see card numbers. Paddle's own buyer terms apply to the purchase.",
  },
  {
    name: "Apple iCloud Mail",
    purpose: "Our support and legal mailboxes. It holds the emails that the institution, its teachers, students or parents send us.",
  },
  {
    name: "ip-api.com",
    purpose: "Receives visitors' IP addresses to derive an approximate country, city and internet provider for operations monitoring.",
  },
  {
    name: "Web search engines (Google, Bing, DuckDuckGo, Yandex and Brave, and where enabled the Brave Search API)",
    purpose: "Originality check: short search queries taken from submitted texts, sent through our self-hosted SearXNG search gateway, and, if that gateway fails, directly to the Brave Search API (where configured) or DuckDuckGo.",
  },
  {
    name: "Sentry",
    purpose: "Error monitoring, if enabled: technical error reports.",
  },
  {
    name: "Discord, Inc.",
    country: "USA",
    purpose: "Operations notices, if enabled: notices of site visits (IP address, approximate location, internet provider, page, referrer and browser) and feedback messages are posted to our private Discord channel.",
  },
];

export default function DataProcessingPage() {
  if (currentLang() === "ru") return <DataProcessingRu />;
  const legalMail = `mailto:${LEGAL.emails.legal}`;

  return (
    <LegalLayout title="Data Processing Terms for Schools and Universities" updated={LEGAL.updated}>
      <section>
        <h2 className="text-ink-100 text-base mb-3">1. Scope and roles</h2>
        <p>
          These terms apply to any school, university or other institution (the "institution") that uses {LEGAL.brand} Classroom. They form part of our{" "}
          <Link to="/terms" className="text-iris hover:underline">Terms of Service</Link> and are provided by {operatorLine()} ("{LEGAL.brand}", "we").
        </p>
        <ul className="list-disc list-inside space-y-1 text-ink-400 mt-3">
          <li>For work handed in to classes, the institution decides why and how student data is processed. The institution is the controller.</li>
          <li>{LEGAL.brand} processes that data only on the institution's behalf. For class work, we are the processor.</li>
          <li>For personal accounts and uploads that are not handed in to a class, our <Link to="/privacy" className="text-iris hover:underline">Privacy Policy</Link> applies instead.</li>
        </ul>
        <p className="mt-3">
          These terms are written for the Law of the Republic of Kazakhstan "On Personal Data and Their Protection" and, for institutions in the EU and the UK, for the data protection rights that apply there.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">2. Subject matter, nature and purpose</h2>
        <ul className="list-disc list-inside space-y-1 text-ink-400">
          <li><strong className="text-ink-300">Subject matter:</strong> running Classroom for the institution: schools, classes, memberships and work handed in by students.</li>
          <li><strong className="text-ink-300">Nature:</strong> storing submitted work; analysing it with AI-content detectors, text signals and an originality check against the {LEGAL.brand} repository and the web; keeping class work in the repository; showing the results to the institution's teachers and admins; and review of some results by our staff (section 5).</li>
          <li><strong className="text-ink-300">Purpose:</strong> helping the institution review whether student work may be AI-generated or copied.</li>
          <li><strong className="text-ink-300">Duration:</strong> for as long as the institution uses Classroom, until the data is deleted as described in section 11.</li>
        </ul>
        <p className="mt-3">
          Our AI models run on our own servers. Student work is not sent to OpenAI, Anthropic, Google or any other external AI provider for analysis, and work handed in to a class is never used to train our models. The only parts of a submitted text that leave our servers for the analysis are the short search queries described in section 7.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">3. Data subjects and categories of data</h2>
        <p>Data subjects:</p>
        <ul className="list-disc list-inside space-y-1 text-ink-400 mt-2">
          <li>Students, including students under 18</li>
          <li>Teachers</li>
          <li>School admins and the school owner</li>
        </ul>
        <p className="mt-3">Categories of data:</p>
        <ul className="list-disc list-inside space-y-1 text-ink-400 mt-2">
          <li><strong className="text-ink-300">Account data:</strong> email address, username, hashed password, optional avatar and bio, email verification status</li>
          <li><strong className="text-ink-300">Class membership:</strong> school name and web address, memberships and roles, class names and class year</li>
          <li><strong className="text-ink-300">Submitted work:</strong> files handed in (images, video, audio, text, PDF, DOCX), text extracted from documents, file metadata (EXIF, XMP, C2PA), file hashes, perceptual hashes, image embeddings and text embeddings used for the originality check</li>
          <li><strong className="text-ink-300">Results:</strong> AI-content scores, verdicts, any verdict corrected by our staff, and text signals such as bypass characters, vocabulary compared with class year and style compared with the student's earlier class work</li>
          <li><strong className="text-ink-300">Originality matches:</strong> matching passages and their sources on the web or in the {LEGAL.brand} repository</li>
          <li><strong className="text-ink-300">Technical data:</strong> IP address, approximate location, internet provider, browser, access and error logs</li>
        </ul>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">4. Instructions</h2>
        <p>
          We process class data only to provide Classroom as the institution uses it and as described in these terms. The institution's settings and actions in the service, such as creating classes, inviting teachers and deleting the school, are its instructions. We do not use class data for any other purpose, and we do not sell it.
        </p>
        <p className="mt-3">
          If the law requires us to process class data in another way, we will tell the institution first unless the law forbids it. If we believe an instruction breaks data protection law, we will tell the institution.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">5. Who can see class data, and security</h2>
        <p>
          Inside the service, teachers see only work handed in to their own classes, never students' personal uploads; school admins see all classes of their school; teachers of the same school do not see each other's classes. Work handed in to a class cannot be made public.
        </p>
        <p className="mt-3">
          Access to production systems is limited to the person who supervises the service. Our staff reviewers can open submissions with split or escalated results, including class work, may correct the verdict, and can see the sources of originality matches. Most results are produced automatically and are not reviewed by a person. Anyone we allow to access class data must keep it confidential.
        </p>
        <p className="mt-3">Security measures in place:</p>
        <ul className="list-disc list-inside space-y-1 text-ink-400 mt-2">
          <li>HTTPS for all traffic</li>
          <li>Passwords stored only as hashes (PBKDF2)</li>
          <li>API keys stored only as SHA-256 hashes; the key itself is shown once</li>
          <li>Webhooks signed with HMAC-SHA256</li>
          <li>Uploaded files kept in private storage and served only through short-lived signed links</li>
          <li>Application servers, database and file storage self-hosted in Kazakhstan</li>
        </ul>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">6. Sub-processors</h2>
        <p>The institution agrees that we may use the following sub-processors and recipients:</p>
        <ul className="list-disc list-inside space-y-2 text-ink-400 mt-2">
          {SUBPROCESSORS.map((s) => (
            <li key={s.name}>
              <strong className="text-ink-300">{s.name}</strong>{s.country ? ` (${s.country})` : ""}: {s.purpose}
            </li>
          ))}
        </ul>
        <p className="mt-3">
          Before a new sub-processor starts processing class data, we will add it to this list and change the date at the top of this page. If the institution objects, it may stop using the service by deleting the school. We may also disclose data where the law requires it, as described in section 4.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">7. International transfers</h2>
        <p>Class data is stored in Kazakhstan. Some data leaves Kazakhstan, or may be stored outside it, in these cases:</p>
        <ul className="list-disc list-inside space-y-1 text-ink-400 mt-2">
          <li><strong className="text-ink-300">Cloudflare:</strong> all traffic, including uploaded work, passes through Cloudflare's network in transit.</li>
          <li><strong className="text-ink-300">Email:</strong> transactional emails, including recipients' email addresses, are sent through Resend on Amazon SES in Ireland. Emails sent to our support and legal addresses are held in Apple iCloud Mail.</li>
          <li><strong className="text-ink-300">Search queries:</strong> for the originality check, up to 8 distinctive sentences of at most 14 words each from a submitted text are sent as search queries to the search engines listed in section 6. Pages found are downloaded from the open web for comparison. For class work this web search is on by default; a school admin can turn it off in the school settings.</li>
          <li><strong className="text-ink-300">Technical data:</strong> visitors' IP addresses are sent to ip-api.com; if error monitoring is enabled, technical error reports are sent to Sentry; and if operations notices are enabled, visit notices and feedback messages are posted to our private Discord channel.</li>
          <li><strong className="text-ink-300">Payments:</strong> if the institution buys a paid plan, Paddle in the United Kingdom handles the payment, taxes and invoices.</li>
        </ul>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">8. Requests from students and parents</h2>
        <p>
          We help the institution answer requests from students, parents and staff to access, correct, delete or restrict their data, as far as the service allows. A student can delete any single piece of work they handed in, or delete their own account, which also deletes all the work they handed in to classes. An account with an active paid subscription can be deleted only after that subscription is cancelled.
        </p>
        <p className="mt-3">
          If we receive a request about class work directly, we will forward it to the institution. For help, write to{" "}
          <a href={legalMail} className="text-iris hover:underline">{LEGAL.emails.legal}</a>. We answer within 30 days.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">9. Personal data breaches</h2>
        <p>
          If a personal data breach affects class data, we will notify the institution by email to the school owner without undue delay, and within 72 hours of becoming aware of it. We will share what we know about the breach, the data affected and the steps we are taking.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">10. The originality repository</h2>
        <ul className="list-disc list-inside space-y-1 text-ink-400">
          <li>Every text, PDF and DOCX submission is compared with the {LEGAL.brand} repository and with the web.</li>
          <li>Work handed in to a class is stored in the repository and compared with future submissions from any institution and with personal uploads by any {LEGAL.brand} user, so that copying between institutions can be found.</li>
          <li>When a submission matches work that the teacher cannot open, for example work from another institution or from another teacher's class, the report shows it only as "Another {LEGAL.brand} submission", with the matching passages of the student's own text and the date the other work was submitted. The teacher never sees the other text, its file name or who wrote it.</li>
          <li>Class work stays in the repository until it is deleted: when the school is deleted, when the student deletes that work or their account, or when its class is deleted with the teacher's account as described in section 11.</li>
          <li>Personal uploads that are not handed in to a class are compared but not added to the repository.</li>
        </ul>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">11. Deletion and return of data</h2>
        <ul className="list-disc list-inside space-y-1 text-ink-400">
          <li>Class work is kept until the school owner deletes the school, until the student deletes that work or their account, or, for a class that is not part of any school, until its teacher deletes their account. It is not deleted automatically after a fixed period.</li>
          <li>When the institution stops using Classroom, the school owner deletes the school. This deletes all classes of the school and all work handed in to them, including their copies in the originality repository.</li>
          <li>If a teacher deletes their own account, the teacher's classes inside a school are handed to the school owner, and the work handed in to them stays with the school. Classes that are not part of any school are deleted together with all work handed in to them. Class work is never turned into a student's personal upload.</li>
          <li>Database backups are kept for 14 days, so deleted data can remain in backups for up to 14 days before it expires.</li>
          <li>Before deleting the school, the institution may ask for a copy of its class data by writing to <a href={legalMail} className="text-iris hover:underline">{LEGAL.emails.legal}</a>.</li>
        </ul>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">12. Your duties as an institution</h2>
        <ul className="list-disc list-inside space-y-1 text-ink-400">
          <li>Have a lawful basis for processing student and staff data with {LEGAL.brand}.</li>
          <li>Where students are under 18, obtain the consent of their parents or legal representatives where the law requires it.</li>
          <li>Tell students, and where relevant their parents, that their work is checked with {LEGAL.brand}, what is checked, that short extracts of texts are sent to web search engines, and that class work is kept in the originality repository.</li>
          <li>Treat AI verdicts, originality matches and text signals as probabilistic. They are reasons to talk to the student, never proof, and {LEGAL.brand} does not guarantee their accuracy.</li>
          <li>Do not base disciplinary or grading decisions solely on {LEGAL.brand} results, and give the student a chance to respond.</li>
          <li>Give access only to teachers and admins who need it, and keep teacher and class codes away from anyone else.</li>
        </ul>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">13. Audits and a signed copy</h2>
        <p>
          On reasonable request, we will provide written information that shows how we meet these terms, such as answers to a security or privacy questionnaire.
        </p>
        <p className="mt-3">
          If your institution needs a signed data processing agreement, email{" "}
          <a href={legalMail} className="text-iris hover:underline">{LEGAL.emails.legal}</a> with the institution's legal name, address and the school owner's email. We will send these terms as a document for signature and return a countersigned copy. Enterprise customers with a separate agreement follow that agreement where it differs.
        </p>
      </section>
    </LegalLayout>
  );
}
