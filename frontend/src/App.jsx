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
import { fetchOverview, triggerPipeline } from './services/api';

export default function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [activeSource, setActiveSource] = useState('all');
  const [overview, setOverview] = useState(null);

  const loadData = async () => {
    try {
      const data = await fetchOverview();
      setOverview(data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleTriggerSample = async () => {
    try {
      await triggerPipeline('products');
      await loadData();
      setActiveTab('pipelines');
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="app-container">
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />

      <div className="main-wrapper">
        <Header
          activeTab={activeTab}
          onRefresh={loadData}
          activeSource={activeSource}
          setActiveSource={setActiveSource}
        />

        <main className="content-body">
          {activeTab === 'overview' && (
            <OverviewView
              overview={overview}
              onNavigate={setActiveTab}
              onTriggerSample={handleTriggerSample}
            />
          )}
          {activeTab === 'onboarding' && <OnboardingView />}
          {activeTab === 'datasets' && <DatasetsView />}
          {activeTab === 'quality' && <QualityView />}
          {activeTab === 'pipelines' && (
            <PipelinesView overview={overview} onRefresh={loadData} />
          )}
          {activeTab === 'assets' && <AssetsView />}
          {activeTab === 'lineage' && <LineageView />}
          {activeTab === 'copilot' && <CopilotView />}
        </main>
      </div>
    </div>
  );
}
