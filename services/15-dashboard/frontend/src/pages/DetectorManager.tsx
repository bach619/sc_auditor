import React, { useState, useEffect, useCallback } from 'react';
import { 
  Box, Typography, Card, CardContent, Button, TextField, 
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Paper, Dialog, DialogTitle, DialogContent, DialogActions,
  IconButton, Chip, Alert, Snackbar, Tabs, Tab
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import CodeIcon from '@mui/icons-material/Code';
import AddIcon from '@mui/icons-material/Add';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';

const API_BASE = process.env.REACT_APP_SCANNER_SLITHER_URL || 'http://localhost:8014';

interface DetectorMeta {
  name: string;
  description: string;
  impact: string;
  file: string;
  loaded_at: string;
}

interface DetectorListResponse {
  built_in_count: number;
  custom_detectors: Record<string, DetectorMeta>;
  total: number;
}

const DetectorManager: React.FC = () => {
  const [detectors, setDetectors] = useState<DetectorListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [openRegister, setOpenRegister] = useState(false);
  const [openSource, setOpenSource] = useState<string | null>(null);
  const [sourceCode, setSourceCode] = useState('');
  const [newDetectorName, setNewDetectorName] = useState('');
  const [newDetectorSource, setNewDetectorSource] = useState('');
  const [snackbar, setSnackbar] = useState<{open: boolean; message: string; severity: 'success' | 'error'}>({
    open: false, message: '', severity: 'success'
  });
  const [tabValue, setTabValue] = useState(0);

  const fetchDetectors = useCallback(async () => {
    try {
      const resp = await fetch(`${API_BASE}/detectors`);
      if (resp.ok) {
        const body = await resp.json();
        setDetectors(body.data);
      }
    } catch (err) {
      console.error('Failed to fetch detectors:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchDetectors(); }, [fetchDetectors]);

  const handleRegister = async () => {
    try {
      const resp = await fetch(
        `${API_BASE}/detectors?name=${encodeURIComponent(newDetectorName)}&source=${encodeURIComponent(newDetectorSource)}`,
        { method: 'POST' }
      );
      if (resp.ok) {
        setSnackbar({ open: true, message: 'Detector registered successfully', severity: 'success' });
        setOpenRegister(false);
        setNewDetectorName('');
        setNewDetectorSource('');
        fetchDetectors();
      } else {
        const err = await resp.json();
        setSnackbar({ open: true, message: err.detail || 'Registration failed', severity: 'error' });
      }
    } catch (err) {
      setSnackbar({ open: true, message: 'Network error', severity: 'error' });
    }
  };

  const handleDelete = async (name: string) => {
    try {
      const resp = await fetch(`${API_BASE}/detectors/${encodeURIComponent(name)}`, { method: 'DELETE' });
      if (resp.ok) {
        setSnackbar({ open: true, message: `Detector '${name}' deleted`, severity: 'success' });
        fetchDetectors();
      }
    } catch (err) {
      setSnackbar({ open: true, message: 'Delete failed', severity: 'error' });
    }
  };

  const handleViewSource = async (name: string) => {
    try {
      const resp = await fetch(`${API_BASE}/detectors/${encodeURIComponent(name)}/source`);
      if (resp.ok) {
        const body = await resp.json();
        setSourceCode(body.data?.source || '// No source available');
        setOpenSource(name);
      }
    } catch (err) {
      setSnackbar({ open: true, message: 'Failed to load source', severity: 'error' });
    }
  };

  const impactColor = (impact: string) => {
    switch (impact.toUpperCase()) {
      case 'HIGH': return 'error';
      case 'MEDIUM': return 'warning';
      case 'LOW': return 'info';
      default: return 'default';
    }
  };

  if (loading) return <Typography>Loading detectors...</Typography>;

  const customList = detectors ? Object.values(detectors.custom_detectors) : [];

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Custom Slither Detectors
      </Typography>
      
      {detectors && (
        <Typography variant="body1" color="text.secondary" gutterBottom>
          {detectors.built_in_count} built-in Slither detectors + {detectors.total} custom
        </Typography>
      )}

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs value={tabValue} onChange={(_, v) => setTabValue(v)}>
          <Tab label="Installed Detectors" />
          <Tab label="Documentation" />
        </Tabs>
      </Box>

      {tabValue === 0 && (
        <>
          <Button 
            variant="contained" 
            startIcon={<AddIcon />} 
            onClick={() => setOpenRegister(true)}
            sx={{ mb: 2 }}
          >
            Register New Detector
          </Button>

          {customList.length === 0 ? (
            <Alert severity="info">
              No custom detectors registered. Click "Register New Detector" to add one.
            </Alert>
          ) : (
            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Name</TableCell>
                    <TableCell>Description</TableCell>
                    <TableCell>Impact</TableCell>
                    <TableCell>File</TableCell>
                    <TableCell>Loaded</TableCell>
                    <TableCell>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {customList.map((det) => (
                    <TableRow key={det.name}>
                      <TableCell><strong>{det.name}</strong></TableCell>
                      <TableCell>{det.description}</TableCell>
                      <TableCell>
                        <Chip label={det.impact} color={impactColor(det.impact)} size="small" />
                      </TableCell>
                      <TableCell>{det.file}</TableCell>
                      <TableCell>{new Date(det.loaded_at).toLocaleString()}</TableCell>
                      <TableCell>
                        <IconButton onClick={() => handleViewSource(det.name)} title="View source">
                          <CodeIcon />
                        </IconButton>
                        <IconButton onClick={() => handleDelete(det.name)} title="Delete detector" color="error">
                          <DeleteIcon />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </>
      )}

      {tabValue === 1 && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>How to Write Custom Detectors</Typography>
            <Typography variant="body2" component="div">
              <pre style={{ background: '#f5f5f5', padding: 16, borderRadius: 8, overflow: 'auto' }}>
{`from slither.detectors.abstract_detector import AbstractDetector, DetectorClassification

class MyDetector(AbstractDetector):
    NAME = "my-detector"
    DESCRIPTION = "Describe what this detector finds"
    IMPACT = DetectorClassification.HIGH
    
    def detect(self):
        results = []
        for contract in self.slither.contracts:
            for func in contract.functions_entry_points:
                # Your detection logic here
                pass
        return results`}
              </pre>
            </Typography>
          </CardContent>
        </Card>
      )}

      {/* Register Dialog */}
      <Dialog open={openRegister} onClose={() => setOpenRegister(false)} maxWidth="md" fullWidth>
        <DialogTitle>Register New Detector</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Detector Name"
            fullWidth
            value={newDetectorName}
            onChange={(e) => setNewDetectorName(e.target.value)}
            sx={{ mb: 2 }}
          />
          <TextField
            label="Python Source Code"
            multiline
            rows={12}
            fullWidth
            value={newDetectorSource}
            onChange={(e) => setNewDetectorSource(e.target.value)}
            sx={{ fontFamily: 'monospace' }}
            placeholder="class MyDetector(AbstractDetector): ..."
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenRegister(false)}>Cancel</Button>
          <Button onClick={handleRegister} variant="contained" disabled={!newDetectorName || !newDetectorSource}>
            Register
          </Button>
        </DialogActions>
      </Dialog>

      {/* Source Dialog */}
      <Dialog open={openSource !== null} onClose={() => setOpenSource(null)} maxWidth="md" fullWidth>
        <DialogTitle>Detector Source: {openSource}</DialogTitle>
        <DialogContent>
          <pre style={{ background: '#f5f5f5', padding: 16, borderRadius: 8, overflow: 'auto', maxHeight: 400 }}>
            {sourceCode}
          </pre>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenSource(null)}>Close</Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
      >
        <Alert severity={snackbar.severity} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default DetectorManager;
