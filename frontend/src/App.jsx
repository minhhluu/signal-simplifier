import React, { useState, useMemo } from 'react';
import 'katex/dist/katex.min.css';
import { BlockMath } from 'react-katex';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Zap, Network, ListTree, HelpCircle, Activity, Cpu, Copy, Check } from 'lucide-react';
import CytoscapeComponent from 'react-cytoscapejs';

const App = () => {
  const [input, setInput] = useState('exp(-u^2*t + i*u*x - i*u*xi)');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedStep, setSelectedStep] = useState(0);
  const [rightPanelTab, setRightPanelTab] = useState('ast'); // 'ast' or 'verilog'
  const [copied, setCopied] = useState(false);
  const [fractionalBits, setFractionalBits] = useState(14);
  const [fuzzing, setFuzzing] = useState(false);
  const [fuzzResult, setFuzzResult] = useState(null);

  const handleSimplify = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('http://localhost:8000/simplify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          expression: input,
          fractional_bits: parseInt(fractionalBits)
        }),
      });
      const data = await response.json();
      if (response.ok) {
        setResult(data);
        setSelectedStep(0);
      } else {
        setError(data.detail || 'Something went wrong');
      }
    } catch (err) {
      setError('Could not connect to backend server');
    } finally {
      setLoading(false);
    }
  };

  const handleFuzz = async () => {
    setFuzzing(true);
    setFuzzResult(null);
    try {
      const response = await fetch('http://localhost:8000/fuzz', { method: 'POST' });
      const data = await response.json();
      setFuzzResult(data);
    } catch (error) {
      console.error('Fuzz error:', error);
    } finally {
      setFuzzing(false);
    }
  };

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const transformToCy = (node, elements = [], parentId = null, counter = { val: 0 }) => {
    const id = `node-${counter.val++}`;
    elements.push({
      data: { id, label: node.name }
    });
    if (parentId) {
      elements.push({
        data: { source: parentId, target: id }
      });
    }
    if (node.children) {
      node.children.forEach(child => transformToCy(child, elements, id, counter));
    }
    return elements;
  };

  const cyElements = useMemo(() => {
    if (!result?.steps[selectedStep]?.tree) return [];
    return transformToCy(result.steps[selectedStep].tree);
  }, [result, selectedStep]);

  const cyLayout = {
    name: 'breadthfirst',
    directed: true,
    padding: 20,
    animate: true,
    spacingFactor: 1.1
  };

  const cyStyle = [
    {
      selector: 'node',
      style: {
        'background-color': '#38bdf8',
        'label': 'data(label)',
        'color': '#ffffff',
        'font-family': 'Inter',
        'font-size': '10px',
        'text-valign': 'center',
        'text-halign': 'center',
        'width': '30px',
        'height': '30px'
      }
    },
    {
      selector: 'edge',
      style: {
        'width': 2,
        'line-color': '#64748b',
        'target-arrow-color': '#64748b',
        'target-arrow-shape': 'triangle',
        'curve-style': 'bezier'
      }
    }
  ];

  return (
    <div className="app-container">
      <header className="header">
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <Activity size={40} color="#38bdf8" style={{ marginBottom: '1rem' }} />
          <h1>Signal Simplifier</h1>
          <p>Rule-based mathematical reduction for Signals & Systems</p>
        </motion.div>
      </header>

      <div className="main-layout">
        <div className="card">
          <h2><Zap size={20} /> Input</h2>
          <div className="input-section">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              spellCheck="false"
              placeholder="Enter expression here..."
            />

            <div className="quick-actions">
              {['exp', 'Sum', 'Integral', 'conj', 'pi', 'oo', 'i', 'u', 'x', 'xi', 't'].map(sym => (
                <button
                  key={sym}
                  className="btn-token"
                  onClick={() => {
                    let insert = sym;
                    if (sym === 'Integral') insert = 'Integral(..., u)';
                    if (sym === 'Sum') insert = 'Sum(..., (k, 0, N-1))';
                    if (sym === 'conj') insert = 'conjugate(...)';
                    setInput(prev => prev + insert);
                  }}
                >
                  {sym === 'pi' ? 'π' : sym === 'xi' ? 'ξ' : sym === 'oo' ? '∞' : sym}
                </button>
              ))}
              <button className="btn-token btn-clear" onClick={() => setInput('')}>Clear</button>
            </div>

            <button className="btn-primary" onClick={handleSimplify} disabled={loading} style={{ width: '100%', marginTop: '1rem' }}>
              {loading ? 'Solving...' : 'Solve Steps'} <Send size={16} />
            </button>

          </div>

          {error && <div className="insight-banner" style={{ background: '#450a0a', borderLeftColor: '#ef4444' }}>{error}</div>}

          <div style={{ marginTop: 'auto', paddingTop: '1.5rem', fontSize: '0.8rem', color: '#94a3b8' }}>
            <p><strong>Examples (Python Syntax):</strong></p>
            <ul style={{ paddingLeft: '1rem', marginTop: '0.5rem' }}>
              <li><code>Sum(X[k] * exp(j*2*pi*k*n/N), (k, 0, N-1)) / N</code></li>
              <li><code>Integral(exp(-u^2), (u, -oo, oo))</code></li>
            </ul>
          </div>
        </div>
        <div className="card">
          <h2><ListTree size={20} /> Reduction Path</h2>
          <div className="steps-container">
            {result?.steps.map((step, idx) => (
              <div
                key={idx}
                className={`step-card ${selectedStep === idx ? 'active' : ''}`}
                onClick={() => setSelectedStep(idx)}
              >
                <div className="step-rule">{step.rule}</div>
                <div className="step-math"><BlockMath math={step.expression} /></div>
              </div>
            ))}
          </div>
          {result?.insight && (
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="insight-banner"
            >
              <HelpCircle size={18} /> {result.insight}
            </motion.div>
          )}
        </div>

        <div className="card">
          <div className="card-header-tabs">
            <h2 onClick={() => setRightPanelTab('ast')} className={rightPanelTab === 'ast' ? 'active-tab' : ''}>
              <Network size={20} /> AST Graph
            </h2>
            <h2 onClick={() => setRightPanelTab('verilog')} className={rightPanelTab === 'verilog' ? 'active-tab' : ''}>
              <Cpu size={18} /> Verilog
            </h2>
            <h2 onClick={() => setRightPanelTab('sv')} className={rightPanelTab === 'sv' ? 'active-tab' : ''}>
              <Zap size={18} /> SystemVerilog
            </h2>
          </div>

          <div className="tree-container">
            {rightPanelTab === 'ast' ? (
              cyElements.length > 0 ? (
                <CytoscapeComponent
                  elements={cyElements}
                  layout={cyLayout}
                  style={{ width: '100%', height: '400px' }}
                  stylesheet={cyStyle}
                  cy={cy => { cy.layout(cyLayout).run(); }}
                />
              ) : (
                <div style={{ textAlign: 'center', opacity: 0.3, marginTop: '2rem' }}>
                  <Activity size={48} style={{ opacity: 0.2, marginBottom: '1rem' }} />
                  <p>Select a step to view tree</p>
                </div>
              )
            ) : rightPanelTab === 'verilog' ? (
              <div className="verilog-container">
                {result?.final_verilog && (
                  <button className="btn-copy" onClick={() => handleCopy(result.final_verilog)}>
                    {copied ? <Check size={14} /> : <Copy size={14} />}
                    {copied ? 'Copied' : 'Copy'}
                  </button>
                )}
                {result?.final_verilog ? (
                  <pre><code>{result.final_verilog}</code></pre>
                ) : (
                  <div style={{ textAlign: 'center', opacity: 0.3, marginTop: '2rem' }}>
                    <Cpu size={48} style={{ opacity: 0.2, marginBottom: '1rem' }} />
                    <p>Solve to generate Verilog</p>
                  </div>
                )}
              </div>
            ) : (
              <div className="verilog-container" style={{ borderLeftColor: '#f59e0b' }}>
                {result?.final_sv && (
                  <button className="btn-copy" onClick={() => handleCopy(result.final_sv)}>
                    {copied ? <Check size={14} /> : <Copy size={14} />}
                    {copied ? 'Copied' : 'Copy'}
                  </button>
                )}
                {result?.final_sv ? (
                  <pre><code>{result.final_sv}</code></pre>
                ) : (
                  <div style={{ textAlign: 'center', opacity: 0.3, marginTop: '2rem' }}>
                    <Zap size={48} style={{ opacity: 0.2, marginBottom: '1rem' }} />
                    <p>Solve to generate SystemVerilog</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default App;
