import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './Layout';
import Dashboard from './pages/Dashboard';
import Agent from './pages/Agent';
import Audits from './pages/Audits';
import AuditDetail from './pages/AuditDetail';
import Programs from './pages/Programs';
import ProgramDetail from './pages/ProgramDetail';
import Settings from './pages/Settings';
import Metrics from './pages/Metrics';
import Daemon from './pages/Daemon';
import Updates from './pages/Updates';
import Feedback from './pages/Feedback';
import ServiceHealth from './pages/ServiceHealth';
import Pipeline from './pages/Pipeline';
import ScannerDetail from './pages/ScannerDetail';
import ExploitViewer from './pages/ExploitViewer';
import ConfigEditor from './pages/ConfigEditor';
import NotifierStatus from './pages/NotifierStatus';
import WebhookLogs from './pages/WebhookLogs';
import SourceViewer from './pages/SourceViewer';
import ReportCenter from './pages/ReportCenter';
import Scheduler from './pages/Scheduler';
import Cases from './pages/Cases';
import CaseDetail from './pages/CaseDetail';
import Archive from './pages/Archive';
import AgentIntelligence from './pages/AgentIntelligence';
import DetectorManager from './pages/DetectorManager';
import NotFound from './pages/NotFound';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/agent" element={<Agent />} />
          <Route path="/agent/intelligence" element={<AgentIntelligence />} />
          <Route path="/audits" element={<Audits />} />
          <Route path="/audits/:id" element={<AuditDetail />} />
          <Route path="/programs" element={<Programs />} />
          <Route path="/programs/:slug" element={<ProgramDetail />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/metrics" element={<Metrics />} />
          <Route path="/daemon" element={<Daemon />} />
          <Route path="/updates" element={<Updates />} />
          <Route path="/feedback" element={<Feedback />} />
          <Route path="/services" element={<ServiceHealth />} />
          <Route path="/pipeline" element={<Pipeline />} />
          <Route path="/scanner" element={<ScannerDetail />} />
          <Route path="/exploit/:findingId" element={<ExploitViewer />} />
          <Route path="/config" element={<ConfigEditor />} />
          <Route path="/notifier" element={<NotifierStatus />} />
          <Route path="/webhooks" element={<WebhookLogs />} />
          <Route path="/source/:auditId" element={<SourceViewer />} />
          <Route path="/reports" element={<ReportCenter />} />
          <Route path="/scheduler" element={<Scheduler />} />
          <Route path="/cases" element={<Cases />} />
          <Route path="/cases/:caseId" element={<CaseDetail />} />
          <Route path="/archive" element={<Archive />} />
          <Route path="/detectors" element={<DetectorManager />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
