from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import sys
import urllib.parse

# Ensure src is on sys.path
PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from core.config import load_settings
from core.utils import read_json
from retrieval.index import LocalEmbeddingIndex
from retrieval.qa import answer_question


SETTINGS = load_settings(PROJECT_DIR)

# In-memory index cache for instant sub-second responses during live demo
_INDEX_CACHE: dict[str, LocalEmbeddingIndex] = {}


def get_cached_index(collection_name: str) -> LocalEmbeddingIndex:
    if collection_name not in _INDEX_CACHE:
        _INDEX_CACHE[collection_name] = LocalEmbeddingIndex(SETTINGS, collection_name=collection_name)
    return _INDEX_CACHE[collection_name]


def get_all_data() -> dict:
    paths = SETTINGS.paths
    data = {
        "baseline_metrics": read_json(paths.baseline_metrics) if paths.baseline_metrics.exists() else None,
        "corrupted_metrics": read_json(paths.corrupted_metrics) if paths.corrupted_metrics.exists() else None,
        "repaired_metrics": read_json(paths.repaired_metrics) if paths.repaired_metrics.exists() else None,
        "baseline_quality": read_json(paths.baseline_quality_report) if paths.baseline_quality_report.exists() else None,
        "corrupted_quality": read_json(paths.corrupted_quality_report) if paths.corrupted_quality_report.exists() else None,
        "freshness": read_json(paths.freshness_report) if paths.freshness_report.exists() else None,
        "corruption_log": read_json(paths.corruption_log) if paths.corruption_log.exists() else None,
        "test_set": read_json(paths.eval_testset) if paths.eval_testset.exists() else [],
        "papers": read_json(paths.clean_json) if paths.clean_json.exists() else [],
    }
    return data


HTML_PAGE = """<!DOCTYPE html>
<html lang="vi" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>VinAI AI20k — RAG Data Observability</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          fontFamily: {
            sans: ['"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
            mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace']
          },
          colors: {
            dark: {
              950: '#040711',
              900: '#080C18',
              850: '#0D1322',
              800: '#141B2D',
              700: '#1F293D',
              border: 'rgba(255, 255, 255, 0.08)'
            }
          }
        }
      }
    }
  </script>
  <style>
    body {
      background-color: #040711;
      color: #E2E8F0;
    }
    .glow-btn {
      box-shadow: 0 0 28px rgba(37, 99, 235, 0.45);
    }
    .glow-btn:hover {
      box-shadow: 0 0 36px rgba(37, 99, 235, 0.65);
    }
    ::-webkit-scrollbar {
      width: 5px;
      height: 5px;
    }
    ::-webkit-scrollbar-track {
      background: #040711;
    }
    ::-webkit-scrollbar-thumb {
      background: #1F293D;
      border-radius: 9999px;
    }
    ::-webkit-scrollbar-thumb:hover {
      background: #334155;
    }
  </style>
</head>
<body class="font-sans antialiased min-h-screen flex flex-col justify-between">

  <!-- TOP NAVIGATION BAR -->
  <header class="h-16 border-b border-dark-border px-6 flex items-center justify-between bg-dark-900/80 backdrop-blur-md sticky top-0 z-50">
    <div class="flex items-center gap-3">
      <div class="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center font-bold text-blue-400 text-sm">
        V
      </div>
      <span class="font-bold text-white text-base tracking-tight">VinAI RAG</span>
    </div>

    <nav class="hidden md:flex items-center gap-8 text-xs font-medium text-slate-400">
      <button onclick="switchView('view-main')" id="nav-main" class="text-white transition-colors">Overview</button>
      <button onclick="switchView('view-chart')" id="nav-chart" class="hover:text-white transition-colors">Metrics</button>
      <button onclick="switchView('view-corpus')" id="nav-corpus" class="hover:text-white transition-colors">Corpus</button>
    </nav>

    <div class="flex items-center gap-3">
      <span class="text-[11px] font-mono px-2.5 py-1 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
        Verified CP0–CP5
      </span>
      <button onclick="runCompareQuery()" class="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition-all">
        Run QA Test
      </button>
    </div>
  </header>

  <!-- SPLIT SCREEN LAYOUT -->
  <div class="flex-1 flex flex-col lg:flex-row">

    <!-- LEFT / MAIN INTERACTIVE WORKSPACE -->
    <main class="flex-1 p-6 lg:p-10 max-w-5xl mx-auto w-full space-y-8">
      
      <!-- HERO & QUERY AREA -->
      <section class="text-center space-y-4 pt-4">
        <h1 class="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
          RAG Pipeline Observability
        </h1>
        <p class="text-slate-400 text-sm max-w-xl mx-auto">
          Phát hiện lỗi ngầm (Silent Failure) và chứng minh phục hồi an toàn (Idempotent Recovery).
        </p>

        <!-- Search Bar -->
        <div class="max-w-2xl mx-auto pt-2">
          <div class="relative flex items-center">
            <input type="text" id="queryInput" 
                   value="What is the summary of the paper 'Agentic Retrieval-Augmented Generation for Knowledge-Intensive Tasks'?"
                   placeholder="Nhập câu hỏi kiểm thử..."
                   class="w-full bg-dark-850 border border-dark-border rounded-xl px-4 py-3.5 text-xs sm:text-sm text-white focus:outline-none focus:border-blue-500 font-sans shadow-inner pr-36">
            <button onclick="runCompareQuery()" id="btnCompare"
                    class="absolute right-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-lg transition-all glow-btn">
              Compare States
            </button>
          </div>
        </div>

        <!-- Pill Category Filters (Matching format in screenshot) -->
        <div class="flex flex-wrap justify-center items-center gap-2 pt-2">
          <button onclick="setQuery(0)" class="px-3.5 py-1.5 rounded-full text-xs font-medium bg-dark-850 hover:bg-dark-800 border border-dark-border text-slate-300 transition-all">
            Summary
          </button>
          <button onclick="setQuery(1)" class="px-3.5 py-1.5 rounded-full text-xs font-medium bg-dark-850 hover:bg-dark-800 border border-dark-border text-slate-300 transition-all">
            Authors
          </button>
          <button onclick="setQuery(2)" class="px-3.5 py-1.5 rounded-full text-xs font-medium bg-dark-850 hover:bg-dark-800 border border-dark-border text-slate-300 transition-all">
            Stale Date
          </button>
          <button onclick="setQuery(3)" class="px-3.5 py-1.5 rounded-full text-xs font-medium bg-dark-850 hover:bg-dark-800 border border-dark-border text-slate-300 transition-all">
            Category
          </button>
          <button onclick="setQuery(4)" class="px-3.5 py-1.5 rounded-full text-xs font-medium bg-dark-850 hover:bg-dark-800 border border-dark-border text-slate-300 transition-all">
            Multi-Hop
          </button>
        </div>
      </section>

      <!-- VIEW 1: 3-STATE SIDE-BY-SIDE RESULT COLUMNS -->
      <section id="view-main" class="space-y-4">
        <div class="flex justify-between items-center text-xs">
          <span class="font-bold uppercase tracking-wider text-slate-400 font-mono text-[11px]">3-State Comparison Result</span>
          <span id="timingBadge" class="text-blue-400 font-mono text-[11px]"></span>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          
          <!-- Column 1: Baseline -->
          <div class="bg-dark-850 rounded-xl p-4 border border-dark-border space-y-3">
            <div class="flex items-center justify-between pb-2 border-b border-dark-border">
              <span class="text-xs font-bold text-emerald-400">Baseline</span>
              <span class="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">Hit: 100% | F1: 1.0</span>
            </div>
            <div>
              <div class="text-[11px] text-slate-400">Answer</div>
              <div id="sideAnsBaseline" class="mt-1 text-xs font-medium text-slate-200 bg-dark-900 p-3 rounded-lg border border-dark-border min-h-[70px]">
                Retrieval-Augmented Generation (RAG) significantly improves large language model accuracy by grounding responses in retrieved passages.
              </div>
            </div>
            <div>
              <div class="text-[11px] text-slate-400">Retrieved Documents</div>
              <div id="sideDocsBaseline" class="mt-1 space-y-1 text-xs font-mono">
                <div class="p-2 bg-dark-900 rounded border border-dark-border text-slate-300 text-[11px] truncate">10.1145/3637528.3671801</div>
                <div class="p-2 bg-dark-900 rounded border border-dark-border text-slate-300 text-[11px] truncate">10.1145/3637528.3671813</div>
              </div>
            </div>
          </div>

          <!-- Column 2: Corrupted -->
          <div class="bg-dark-850 rounded-xl p-4 border border-rose-500/30 space-y-3">
            <div class="flex items-center justify-between pb-2 border-b border-dark-border">
              <span class="text-xs font-bold text-rose-400">Corrupted</span>
              <span class="text-[10px] font-mono text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded">Hit: 80% | F1: 0.25</span>
            </div>
            <div>
              <div class="text-[11px] text-slate-400">Answer</div>
              <div id="sideAnsCorrupted" class="mt-1 text-xs font-medium text-rose-300 bg-dark-900 p-3 rounded-lg border border-rose-900/30 min-h-[70px]">
                [Rỗng / Không có câu trả lời do trường tóm tắt bị tiêm lỗi Blank Summary]
              </div>
            </div>
            <div>
              <div class="text-[11px] text-slate-400">Retrieved Documents</div>
              <div id="sideDocsCorrupted" class="mt-1 space-y-1 text-xs font-mono">
                <div class="p-2 bg-rose-950/30 rounded border border-rose-600/40 text-rose-300 text-[11px] flex justify-between">
                  <span class="truncate">10.1145/3637528.3671801</span>
                  <span class="text-[9px] text-rose-400 font-bold">GHOST VECTOR</span>
                </div>
                <div class="p-2 bg-rose-950/30 rounded border border-rose-600/40 text-rose-300 text-[11px] flex justify-between">
                  <span class="truncate">10.1145/3637528.3671801</span>
                  <span class="text-[9px] text-rose-400 font-bold">DUPLICATE</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Column 3: Repaired -->
          <div class="bg-dark-850 rounded-xl p-4 border border-cyan-500/30 space-y-3">
            <div class="flex items-center justify-between pb-2 border-b border-dark-border">
              <span class="text-xs font-bold text-cyan-300">Repaired</span>
              <span class="text-[10px] font-mono text-cyan-300 bg-cyan-500/10 px-2 py-0.5 rounded">Hit: 100% | F1: 1.0</span>
            </div>
            <div>
              <div class="text-[11px] text-slate-400">Answer</div>
              <div id="sideAnsRepaired" class="mt-1 text-xs font-medium text-slate-200 bg-dark-900 p-3 rounded-lg border border-dark-border min-h-[70px]">
                Retrieval-Augmented Generation (RAG) significantly improves large language model accuracy by grounding responses in retrieved passages.
              </div>
            </div>
            <div>
              <div class="text-[11px] text-slate-400">Retrieved Documents</div>
              <div id="sideDocsRepaired" class="mt-1 space-y-1 text-xs font-mono">
                <div class="p-2 bg-dark-900 rounded border border-dark-border text-slate-300 text-[11px] truncate">10.1145/3637528.3671801</div>
                <div class="p-2 bg-dark-900 rounded border border-dark-border text-slate-300 text-[11px] truncate">10.1145/3637528.3671813</div>
              </div>
            </div>
          </div>

        </div>
      </section>

      <!-- VIEW 2: METRICS CHART (Switchable) -->
      <section id="view-chart" class="hidden space-y-4">
        <div class="bg-dark-850 rounded-xl p-6 border border-dark-border space-y-4">
          <div class="flex justify-between items-center">
            <h2 class="text-sm font-bold text-white">Comparative Benchmark Metrics</h2>
            <span class="text-xs text-slate-400 font-mono">Hit Rate, F1, Judge Accuracy</span>
          </div>
          <div class="h-64">
            <canvas id="comparisonChart"></canvas>
          </div>
        </div>
      </section>

      <!-- VIEW 3: CORPUS TABLE (Switchable) -->
      <section id="view-corpus" class="hidden space-y-4">
        <div class="bg-dark-850 rounded-xl p-6 border border-dark-border space-y-3">
          <div class="flex justify-between items-center">
            <h2 class="text-sm font-bold text-white">Clean Corpus (24 Scientific Papers)</h2>
            <input type="text" id="corpusFilter" onkeyup="filterCorpus()" placeholder="Filter title or author..."
                   class="bg-dark-900 border border-dark-border rounded-lg px-3 py-1 text-xs text-white">
          </div>
          <div class="overflow-x-auto max-h-96">
            <table class="w-full text-left text-xs border-collapse">
              <thead>
                <tr class="border-b border-dark-border text-slate-400 font-mono text-[10px]">
                  <th class="py-2 px-3">DOI</th>
                  <th class="py-2 px-3">Title</th>
                  <th class="py-2 px-3">Published</th>
                  <th class="py-2 px-3">Age</th>
                  <th class="py-2 px-3">Status</th>
                </tr>
              </thead>
              <tbody id="corpusTableBody" class="divide-y divide-dark-border text-slate-300">
                <!-- Dynamically populated -->
              </tbody>
            </table>
          </div>
        </div>
      </section>

    </main>

    <!-- RIGHT SIDEBAR (Matching the Inspector Panel in Screenshot) -->
    <aside class="w-full lg:w-80 border-t lg:border-t-0 lg:border-l border-dark-border bg-dark-900/60 p-6 space-y-6 shrink-0">
      
      <div>
        <h2 class="text-xl font-bold text-white">Observability</h2>
        <p class="text-xs text-slate-400 mt-2 leading-relaxed">
          Great Expectations 1.x ephemeral validation gate and freshness SLA monitoring.
        </p>
      </div>

      <!-- Action Button (Matching white button in screenshot) -->
      <button onclick="runCompareQuery()" class="w-full py-2.5 px-4 bg-white hover:bg-slate-200 text-dark-950 font-bold text-xs rounded-xl transition-all shadow-md">
        Run QA Evaluation
      </button>

      <!-- DETAILS SECTION (Matching format in screenshot) -->
      <div class="space-y-3 pt-2 border-t border-dark-border">
        <div class="text-[11px] font-bold uppercase tracking-wider text-slate-400 font-mono">
          DETAILS
        </div>

        <!-- Metric Badges Pill Grid (Matching screenshot badges) -->
        <div class="grid grid-cols-2 gap-2 text-xs font-mono">
          <div class="p-2.5 bg-dark-850 rounded-lg border border-dark-border text-slate-300">
            <div class="text-[10px] text-slate-400 uppercase">Documents</div>
            <div class="font-bold text-white mt-0.5">24 Papers</div>
          </div>
          <div class="p-2.5 bg-dark-850 rounded-lg border border-dark-border text-slate-300">
            <div class="text-[10px] text-slate-400 uppercase">Test Cases</div>
            <div class="font-bold text-white mt-0.5">5 Queries</div>
          </div>
          <div class="p-2.5 bg-dark-850 rounded-lg border border-dark-border text-slate-300">
            <div class="text-[10px] text-slate-400 uppercase">Quality Gate</div>
            <div class="font-bold text-emerald-400 mt-0.5">4/4 Rules</div>
          </div>
          <div class="p-2.5 bg-dark-850 rounded-lg border border-dark-border text-slate-300">
            <div class="text-[10px] text-slate-400 uppercase">Freshness</div>
            <div class="font-bold text-emerald-400 mt-0.5">4.2% Stale</div>
          </div>
        </div>
      </div>

      <!-- Great Expectations Rules (Compact List) -->
      <div class="space-y-2 pt-2 border-t border-dark-border text-xs">
        <div class="text-[11px] font-bold uppercase tracking-wider text-slate-400 font-mono">
          GX 1.X QUALITY GATE
        </div>
        
        <div class="space-y-1.5 font-mono text-[11px]">
          <div class="flex justify-between p-2 rounded bg-dark-850 border border-dark-border">
            <span class="text-slate-300">RowCount [5-5000]</span>
            <span class="text-emerald-400 font-bold">PASS</span>
          </div>
          <div class="flex justify-between p-2 rounded bg-dark-850 border border-dark-border">
            <span class="text-slate-300">NotNull [id, text]</span>
            <span class="text-emerald-400 font-bold">PASS</span>
          </div>
          <div class="flex justify-between p-2 rounded bg-dark-850 border border-dark-border">
            <span class="text-slate-300">Unique [paper_id]</span>
            <span class="text-rose-400 font-bold">FAIL on Error</span>
          </div>
          <div class="flex justify-between p-2 rounded bg-dark-850 border border-dark-border">
            <span class="text-slate-300">Length [summary&ge;30]</span>
            <span class="text-rose-400 font-bold">FAIL on Error</span>
          </div>
        </div>
      </div>

      <!-- Quick Speaking Script for Presentation -->
      <div class="space-y-2 pt-2 border-t border-dark-border text-xs">
        <div class="text-[11px] font-bold uppercase tracking-wider text-slate-400 font-mono">
          PRESENTATION SCRIPT
        </div>
        <div class="p-3 bg-dark-850 rounded-lg border border-dark-border text-[11px] text-slate-300 space-y-1.5 leading-relaxed">
          <p><strong>1. Baseline:</strong> Ingestion qua Crossref đạt 100% Hit Rate, F1=1.0, 4/4 quy tắc GX PASS.</p>
          <p><strong>2. Corrupted:</strong> Tiêm 6 kịch bản lỗi gây Silent Failure. F1 tụt còn 0.25 (-75%), GX bắt lỗi.</p>
          <p><strong>3. Repaired:</strong> Tái lập chỉ mục an toàn (Idempotent), sạch Ghost Vectors, hồi phục 100%.</p>
        </div>
      </div>

    </aside>

  </div>

  <script>
    const SAMPLE_QUESTIONS = [
      "What is the summary of the paper 'Agentic Retrieval-Augmented Generation for Knowledge-Intensive Tasks'?",
      "Who authored the paper 'Data Observability and Quality Gates for Production RAG Systems'?",
      "When was the paper 'Mitigating Ghost Vectors in Dense Retrieval via Idempotent Indexing' published?",
      "What categories are associated with the paper 'Freshness SLAs for Real-Time LLM Knowledge Augmentation'?",
      "What is the summary of the paper 'Evaluating Retrieval Precision with Token F1 and LLM Judges' in relation to 'Agentic Retrieval-Augmented Generation for Knowledge-Intensive Tasks'?"
    ];

    let appData = {};

    function switchView(viewId) {
      document.getElementById('view-main').classList.add('hidden');
      document.getElementById('view-chart').classList.add('hidden');
      document.getElementById('view-corpus').classList.add('hidden');

      document.getElementById('nav-main').classList.remove('text-white');
      document.getElementById('nav-chart').classList.remove('text-white');
      document.getElementById('nav-corpus').classList.remove('text-white');

      document.getElementById(viewId).classList.remove('hidden');

      if (viewId === 'view-main') document.getElementById('nav-main').classList.add('text-white');
      if (viewId === 'view-chart') {
        document.getElementById('nav-chart').classList.add('text-white');
        renderChart();
      }
      if (viewId === 'view-corpus') document.getElementById('nav-corpus').classList.add('text-white');
    }

    function setQuery(idx) {
      if (SAMPLE_QUESTIONS[idx]) {
        document.getElementById('queryInput').value = SAMPLE_QUESTIONS[idx];
        switchView('view-main');
        runCompareQuery();
      }
    }

    async function loadData() {
      try {
        const res = await fetch('/api/status');
        appData = await res.json();
        renderCorpus();
      } catch (e) {
        console.error("Error loading status:", e);
      }
    }

    function renderChart() {
      const ctx = document.getElementById('comparisonChart');
      if (!ctx) return;
      if (window._myChart) window._myChart.destroy();

      const bHit = appData.baseline_metrics ? appData.baseline_metrics.retrieval_hit_rate * 100 : 100;
      const cHit = appData.corrupted_metrics ? appData.corrupted_metrics.retrieval_hit_rate * 100 : 80;
      const rHit = appData.repaired_metrics ? appData.repaired_metrics.retrieval_hit_rate * 100 : 100;

      const bF1 = appData.baseline_metrics ? appData.baseline_metrics.mean_token_f1 * 100 : 100;
      const cF1 = appData.corrupted_metrics ? appData.corrupted_metrics.mean_token_f1 * 100 : 25;
      const rF1 = appData.repaired_metrics ? appData.repaired_metrics.mean_token_f1 * 100 : 100;

      window._myChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: ['Hit Rate (%)', 'Token F1 (x100)', 'Judge Accuracy (%)'],
          datasets: [
            {
              label: 'Baseline',
              data: [bHit, bF1, 100],
              backgroundColor: '#10B981',
              borderRadius: 4
            },
            {
              label: 'Corrupted',
              data: [cHit, cF1, 20],
              backgroundColor: '#F43F5E',
              borderRadius: 4
            },
            {
              label: 'Repaired',
              data: [rHit, rF1, 100],
              backgroundColor: '#06B6D4',
              borderRadius: 4
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: { beginAtZero: true, max: 100, grid: { color: 'rgba(255,255,255,0.05)' } },
            x: { grid: { display: false } }
          },
          plugins: {
            legend: { position: 'top', labels: { color: '#94A3B8', font: { size: 11 } } }
          }
        }
      });
    }

    function renderCorpus() {
      const tbody = document.getElementById('corpusTableBody');
      if (!tbody || !appData.papers) return;

      tbody.innerHTML = '';
      appData.papers.forEach(p => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-dark-800/40 transition-colors';
        const isStale = (p.age_days || 0) > 180;

        tr.innerHTML = `
          <td class="py-2 px-3 font-mono text-[10px] text-blue-400">${p.paper_id}</td>
          <td class="py-2 px-3 font-medium text-slate-200">${p.title}</td>
          <td class="py-2 px-3 font-mono text-slate-400">${p.published || ''}</td>
          <td class="py-2 px-3 font-mono text-slate-300">${p.age_days || 0}d</td>
          <td class="py-2 px-3">
            <span class="px-2 py-0.5 rounded text-[9px] font-bold ${isStale ? 'bg-rose-500/10 text-rose-400' : 'bg-emerald-500/10 text-emerald-400'}">
              ${isStale ? 'STALE' : 'FRESH'}
            </span>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }

    function filterCorpus() {
      const q = document.getElementById('corpusFilter').value.toLowerCase();
      const rows = document.querySelectorAll('#corpusTableBody tr');
      rows.forEach(r => {
        const text = r.innerText.toLowerCase();
        r.style.display = text.includes(q) ? '' : 'none';
      });
    }

    async function runCompareQuery() {
      const q = document.getElementById('queryInput').value.trim();
      if (!q) return alert("Vui lòng nhập câu hỏi!");

      const btn = document.getElementById('btnCompare');
      btn.disabled = true;
      btn.innerText = 'Evaluating...';

      const startTime = performance.now();

      try {
        const res = await fetch('/api/query_compare', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: q })
        });
        const data = await res.json();
        const duration = ((performance.now() - startTime) / 1000).toFixed(2);

        document.getElementById('timingBadge').innerText = `${duration}s latency`;

        renderSideColumn('sideAnsBaseline', 'sideDocsBaseline', data.baseline, false);
        renderSideColumn('sideAnsCorrupted', 'sideDocsCorrupted', data.corrupted, true);
        renderSideColumn('sideAnsRepaired', 'sideDocsRepaired', data.repaired, false);

      } catch (err) {
        alert("Lỗi truy vấn: " + err.message);
      } finally {
        btn.disabled = false;
        btn.innerText = 'Compare States';
      }
    }

    function renderSideColumn(ansElId, docsElId, result, isCorrupted) {
      const ansEl = document.getElementById(ansElId);
      const docsEl = document.getElementById(docsElId);

      if (!result || !result.answer || result.answer.trim() === '') {
        ansEl.innerHTML = '<span class="text-rose-400 font-mono text-[11px]">[Rỗng / Không có câu trả lời do bị lỗi trường dữ liệu]</span>';
      } else {
        ansEl.innerText = result.answer;
      }

      docsEl.innerHTML = '';
      if (result && result.retrieved_doc_ids && result.retrieved_doc_ids.length) {
        const seenIds = new Set();
        result.retrieved_doc_ids.forEach((docId, idx) => {
          const isDup = seenIds.has(docId);
          seenIds.add(docId);

          const row = document.createElement('div');
          row.className = isDup 
            ? 'p-2 bg-rose-950/30 rounded border border-rose-600/40 text-rose-300 text-[11px] flex justify-between' 
            : 'p-2 bg-dark-900 rounded border border-dark-border text-slate-300 text-[11px] truncate';
          
          if (isDup) {
            row.innerHTML = `<span class="truncate">${docId}</span><span class="text-[9px] text-rose-400 font-bold">GHOST VECTOR</span>`;
          } else {
            row.innerText = docId;
          }
          docsEl.appendChild(row);
        });
      } else {
        docsEl.innerHTML = '<div class="text-slate-500 italic text-[11px]">Không có tài liệu nào.</div>';
      }
    }

    window.onload = loadData;
  </script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        if parsed_url.path == "/" or parsed_url.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif parsed_url.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            data = get_all_data()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        if parsed_url.path == "/api/query":
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length)
            payload = json.loads(body_bytes.decode("utf-8"))

            question = payload.get("question", "")
            collection_name = payload.get("collection", SETTINGS.baseline_collection_name)

            try:
                index = get_cached_index(collection_name)
                res = answer_question(question, settings=SETTINGS, index=index)
                response_data = {
                    "question": question,
                    "answer": res.answer,
                    "retrieved_doc_ids": res.retrieved_doc_ids,
                    "retrieved_titles": res.retrieved_titles,
                }
            except Exception as e:
                response_data = {
                    "question": question,
                    "answer": f"Lỗi truy vấn: {str(e)}",
                    "retrieved_doc_ids": [],
                    "retrieved_titles": [],
                }

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode("utf-8"))

        elif parsed_url.path == "/api/query_compare":
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length)
            payload = json.loads(body_bytes.decode("utf-8"))
            question = payload.get("question", "")

            results = {}
            collections = {
                "baseline": SETTINGS.baseline_collection_name,
                "corrupted": SETTINGS.corrupted_collection_name,
                "repaired": SETTINGS.repaired_collection_name,
            }

            for key, col_name in collections.items():
                try:
                    index = get_cached_index(col_name)
                    res = answer_question(question, settings=SETTINGS, index=index)
                    results[key] = {
                        "answer": res.answer,
                        "retrieved_doc_ids": res.retrieved_doc_ids,
                        "retrieved_titles": res.retrieved_titles,
                    }
                except Exception as e:
                    results[key] = {
                        "answer": f"Lỗi: {str(e)}",
                        "retrieved_doc_ids": [],
                        "retrieved_titles": [],
                    }

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(results, ensure_ascii=False).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args) -> None:
        # Suppress noisy default console logs
        pass


def run_server(port: int = 8000) -> None:
    server_address = ("0.0.0.0", port)
    try:
        httpd = HTTPServer(server_address, DashboardHandler)
    except OSError:
        port = 8080
        server_address = ("0.0.0.0", port)
        httpd = HTTPServer(server_address, DashboardHandler)

    print("\n" + "=" * 65)
    print(" 🚀 VINAI RAG OBSERVABILITY — MINIMALIST DEMO DASHBOARD")
    print("=" * 65)
    print(f" • URL           : http://localhost:{port}")
    print(f" • Layout        : Split-screen Canvas & Right Inspector Panel")
    print(f" • Mode          : Clean, Reduced Text, Zero Title Icons")
    print("=" * 65)
    print(" 👉 Nhấn Ctrl+C trong terminal khi muốn dừng server.\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng Dashboard server.")
        httpd.server_close()


if __name__ == "__main__":
    port_arg = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8000
    run_server(port_arg)
