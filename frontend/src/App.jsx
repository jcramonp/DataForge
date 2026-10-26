import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import OverviewView from './views/OverviewView';
import OnboardingView from './views/OnboardingView';
import DatasetsView from './views/DatasetsView';
import QualityView from './views/QualityView';
import PipelinesView from './views/PipelinesView';
import AssetsView from './views/AssetsView';
import LineageView from './views/LineageView';
import CopilotView from './views/CopilotView';
import { fetchOverview, fetchSources } from './services/api';
import { sourceKey, sourceScope } from './services/scope';

export default function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [activeSource, setActiveSource] = useState('all');
  const [overview, setOverview] = useState(null);
  const [sources, setSources] = useState([]);
  const [connected, setConnected] = useState(null);
  const [error, setError] = useState(null);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [metadataVersion, setMetadataVersion] = useState(0);
  const scope = sourceScope(sources.find((source) => sourceKey(source) === activeSource));


  const refreshMetadata = () => setMetadataVersion((version) => version + 1);
  const loadData = () => {
    setRefreshVersion((version) => version + 1);
    refreshMetadata();
  };

  useEffect(() => {
    let cancelled = false;
    setOverview(null);
    setError(null);
    async function load() {
      try {
        const rows = await fetchSources();
        const selected = rows.find((source) => sourceKey(source) === activeSource);
        const data = await fetchOverview(sourceScope(selected));
        if (cancelled) return;
        setSources(rows);
        if (activeSource !== 'all' && !selected) setActiveSource('all');
        setOverview(data);
        setConnected(true);
      } catch (err) {
        if (!cancelled) {
          setOverview(null);
          setError(err.message);
          setConnected(false);
        }
      }
    }
    load();
    const timer = setInterval(load, 30000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [activeSource, metadataVersion]);

  return (
    <div className="app-container">
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />

      <div className="main-wrapper">
        <Header
          activeTab={activeTab}
          sources={sources}
          connected={connected}
          onRefresh={loadData}
          activeSource={activeSource}
          setActiveSource={setActiveSource}
        />

        <main className="content-body">
          {error && <div role="alert" className="card">{error}</div>}
          <div key={['onboarding', 'copilot'].includes(activeTab) ? activeTab : `${activeSource}:${refreshVersion}`}>

          {activeTab === 'overview' && (
            <OverviewView
              overview={overview}
              error={error}
              onNavigate={setActiveTab}
              onChoosePipeline={() => setActiveTab('pipelines')}
            />
          )}
          {activeTab === 'onboarding' && <OnboardingView onRegistered={refreshMetadata} />}
          {activeTab === 'datasets' && <DatasetsView scope={scope} />}
          {activeTab === 'quality' && <QualityView scope={scope} />}
          {activeTab === 'pipelines' && (
            <PipelinesView scope={scope} onRefresh={refreshMetadata} />
          )}
          {activeTab === 'assets' && <AssetsView scope={scope} />}
          {activeTab === 'lineage' && <LineageView scope={scope} />}
          {activeTab === 'copilot' && <CopilotView />}
          </div>
        </main>
      </div>
    </div>
  );
}
