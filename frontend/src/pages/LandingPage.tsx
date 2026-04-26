import { Link } from "react-router-dom";

const FEATURES = [
  {
    icon: "🔬",
    title: "Multi-layer ML Detection",
    desc: "ELA, CLIP classifier, spectrogram analysis, LLM vision — all running in parallel on every submission.",
  },
  {
    icon: "🗺",
    title: "Provenance Tracking",
    desc: "Reverse image search, perceptual hash lookup, and C2PA metadata extraction to trace content origin.",
  },
  {
    icon: "📋",
    title: "Fact-Check Pipeline",
    desc: "Extracts verifiable claims from text and cross-references them against live web sources.",
  },
  {
    icon: "👥",
    title: "Community Database",
    desc: "Vote on submissions. Confirmed fakes are indexed and matched against future uploads via perceptual hashing.",
  },
  {
    icon: "📄",
    title: "Forensic PDF Reports",
    desc: "Download a structured report documenting every analyzer result, suitable for editorial or legal review.",
  },
  {
    icon: "🔌",
    title: "Embeddable Widget",
    desc: "Drop a single script tag on any site to display a real-time verification badge.",
  },
];

const SUPPORTED = [
  { label: "Image", formats: "JPEG · PNG · WebP" },
  { label: "Video", formats: "MP4 · MOV · AVI · MKV · WebM" },
  { label: "Audio", formats: "MP3 · WAV · OGG · FLAC" },
  { label: "Text", formats: "Plain text" },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white font-sans">
      <header className="border-b border-gray-100">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <span className="text-xl font-extrabold tracking-tight">
            Proof<span className="text-blue-600">Layer</span>
          </span>
          <div className="flex items-center gap-3">
            <Link to="/login" className="text-sm text-gray-600 hover:text-gray-900">
              Sign in
            </Link>
            <Link
              to="/register"
              className="text-sm px-4 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Get started
            </Link>
          </div>
        </div>
      </header>

      <main>
        <section className="max-w-3xl mx-auto px-6 py-24 text-center">
          <div className="inline-flex items-center gap-2 text-xs font-semibold text-blue-700 bg-blue-50 px-3 py-1 rounded-full mb-6">
            Multi-modal AI content verification
          </div>
          <h1 className="text-5xl font-extrabold tracking-tight text-gray-900 leading-tight mb-6">
            Is it real?<br />
            <span className="text-blue-600">Find out in seconds.</span>
          </h1>
          <p className="text-lg text-gray-500 mb-10 max-w-xl mx-auto">
            ProofLayer runs multiple independent AI detectors on images, video, audio, and text —
            then aggregates the results into a single confidence score with full evidence.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Link
              to="/register"
              className="px-6 py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 text-sm"
            >
              Verify content free →
            </Link>
            <a
              href="/api/docs/"
              className="px-6 py-3 bg-gray-100 text-gray-700 font-semibold rounded-xl hover:bg-gray-200 text-sm"
            >
              API docs
            </a>
          </div>
        </section>

        <section className="border-t border-gray-100 bg-gray-50 py-16">
          <div className="max-w-5xl mx-auto px-6">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-widest text-center mb-8">
              Supported formats
            </p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {SUPPORTED.map((s) => (
                <div key={s.label} className="bg-white rounded-xl p-5 border border-gray-100 text-center">
                  <p className="font-bold text-gray-800 mb-1">{s.label}</p>
                  <p className="text-xs text-gray-400">{s.formats}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="max-w-5xl mx-auto px-6 py-20">
          <h2 className="text-3xl font-extrabold text-gray-900 text-center mb-12">
            Everything in one place
          </h2>
          <div className="grid md:grid-cols-3 gap-6">
            {FEATURES.map((f) => (
              <div key={f.title} className="p-6 border border-gray-100 rounded-2xl hover:border-blue-100 hover:bg-blue-50/30 transition-colors">
                <div className="text-3xl mb-3">{f.icon}</div>
                <h3 className="font-bold text-gray-900 mb-2">{f.title}</h3>
                <p className="text-sm text-gray-500 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="bg-gray-900 text-white py-20 text-center">
          <div className="max-w-xl mx-auto px-6">
            <h2 className="text-3xl font-extrabold mb-4">
              Embeddable widget
            </h2>
            <p className="text-gray-400 mb-8 text-sm">
              Add a verification badge to any website with a single line of HTML.
            </p>
            <pre className="bg-gray-800 text-green-400 text-xs rounded-xl p-4 text-left overflow-x-auto mb-8">
{`<script src="https://prooflayer.app/widget.js"></script>
<div data-prooflayer-id="YOUR_SUBMISSION_ID"></div>`}
            </pre>
            <Link
              to="/register"
              className="inline-block px-6 py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 text-sm"
            >
              Get your API key →
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-gray-100 py-8 text-center text-xs text-gray-400">
        © {new Date().getFullYear()} ProofLayer · Built with Django + React ·{" "}
        <a href="/api/docs/" className="hover:text-gray-600">API docs</a>
      </footer>
    </div>
  );
}
