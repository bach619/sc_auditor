package client

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/antangpatahumahagalewu-stack/sc_auditor/internal/config"
)

// Client is the HTTP client for Vyper backend services.
type Client struct {
	httpClient *http.Client
	cfg        *config.Config
}

// New creates a new Client with the given configuration.
func New(cfg *config.Config) *Client {
	return &Client{
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
			Transport: &http.Transport{
				MaxIdleConns:        10,
				IdleConnTimeout:     30 * time.Second,
				DisableCompression:  false,
			},
		},
		cfg: cfg,
	}
}

// request sends an HTTP request and returns the response body.
func (c *Client) request(method, url string, body interface{}) ([]byte, error) {
	var reqBody io.Reader
	if body != nil {
		data, err := json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("marshaling request body: %w", err)
		}
		reqBody = bytes.NewReader(data)
	}

	req, err := http.NewRequest(method, url, reqBody)
	if err != nil {
		return nil, fmt.Errorf("creating request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("sending request: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("reading response: %w", err)
	}

	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("API error %d: %s", resp.StatusCode, string(respBody))
	}

	return respBody, nil
}

// HealthCheck checks the health of a service.
func (c *Client) HealthCheck(baseURL string) (map[string]interface{}, error) {
	data, err := c.request("GET", baseURL+"/health", nil)
	if err != nil {
		return nil, err
	}

	var result map[string]interface{}
	if err := json.Unmarshal(data, &result); err != nil {
		return nil, fmt.Errorf("parsing health response: %w", err)
	}
	return result, nil
}

// AuditResult represents the result of an audit.
type AuditResult struct {
	AuditID string `json:"audit_id"`
	State   string `json:"state"`
	Address string `json:"address"`
	Chain   string `json:"chain"`
}

// StartAudit starts a new audit for a contract address.
func (c *Client) StartAudit(address, chain, program string, priority int) (*AuditResult, error) {
	payload := map[string]interface{}{
		"address":  address,
		"chain":    chain,
		"program":  program,
		"priority": priority,
	}

	data, err := c.request("POST", c.cfg.OrchestratorURL+"/audit", payload)
	if err != nil {
		return nil, err
	}

	var result AuditResult
	if err := json.Unmarshal(data, &result); err != nil {
		return nil, fmt.Errorf("parsing audit response: %w", err)
	}
	return &result, nil
}

// GetAudit retrieves the status of an audit.
func (c *Client) GetAudit(auditID string) (map[string]interface{}, error) {
	data, err := c.request("GET", c.cfg.OrchestratorURL+"/audit/"+auditID, nil)
	if err != nil {
		return nil, err
	}

	var result map[string]interface{}
	if err := json.Unmarshal(data, &result); err != nil {
		return nil, fmt.Errorf("parsing audit response: %w", err)
	}
	return result, nil
}

// ListAudits retrieves all audits with optional filters.
func (c *Client) ListAudits(state string, limit int) ([]map[string]interface{}, error) {
	url := fmt.Sprintf("%s/audits?limit=%d", c.cfg.OrchestratorURL, limit)
	if state != "" {
		url += "&state=" + state
	}

	data, err := c.request("GET", url, nil)
	if err != nil {
		return nil, err
	}

	var result []map[string]interface{}
	if err := json.Unmarshal(data, &result); err != nil {
		return nil, fmt.Errorf("parsing audits response: %w", err)
	}
	return result, nil
}
