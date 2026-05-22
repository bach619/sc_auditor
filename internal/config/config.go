package config

import (
	"fmt"
	"os"
	"path/filepath"

	"gopkg.in/yaml.v3"
)

// DefaultConfig holds all default configuration values.
var DefaultConfig = Config{
	OrchestratorURL: "http://localhost:8009",
	ScannerURL:      "http://localhost:8003",
	ExploitURL:      "http://localhost:8006",
	ReporterURL:     "http://localhost:8007",
	NotifierURL:     "http://localhost:8008",
	SourceURL:       "http://localhost:8002",
	ImmunefiURL:     "http://localhost:8001",
	ProjectDir:      "",
	OutputFormat:    "rich",
	Color:           true,
	ShowProgress:    true,
	ComposeFile:     "docker-compose.yml",
	ProjectName:     "sc_auditor",
}

// Config represents the Vyper CLI configuration.
type Config struct {
	OrchestratorURL string `yaml:"orchestrator_url"`
	ScannerURL      string `yaml:"scanner_url"`
	ExploitURL      string `yaml:"exploit_url"`
	ReporterURL     string `yaml:"reporter_url"`
	NotifierURL     string `yaml:"notifier_url"`
	SourceURL       string `yaml:"source_url"`
	ImmunefiURL     string `yaml:"immunefi_url"`
	ProjectDir      string `yaml:"project_dir"`
	OutputFormat    string `yaml:"output_format"`
	Color           bool   `yaml:"color"`
	ShowProgress    bool   `yaml:"show_progress"`
	ComposeFile     string `yaml:"compose_file"`
	ProjectName     string `yaml:"project_name"`

	// API Keys
	OpenAIKey    string `yaml:"openai_key"`
	AnthropicKey string `yaml:"anthropic_key"`
	DeepseekKey  string `yaml:"deepseek_key"`
}

// ConfigPath returns the default config file path.
func ConfigPath() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return filepath.Join(".vyper", "config.yml")
	}
	return filepath.Join(home, ".vyper", "config.yml")
}

// Load reads configuration from a YAML file, merging with defaults.
func Load(path string) (*Config, error) {
	cfg := DefaultConfig
	cfg.applyDefaults()

	if path == "" {
		path = ConfigPath()
	}

	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return &cfg, nil // No config file, use defaults
		}
		return nil, fmt.Errorf("reading config: %w", err)
	}

	var fileCfg Config
	if err := yaml.Unmarshal(data, &fileCfg); err != nil {
		return nil, fmt.Errorf("parsing config: %w", err)
	}

	// Merge: file values override defaults
	cfg.merge(&fileCfg)
	return &cfg, nil
}

// Save writes configuration to a YAML file.
func Save(path string, cfg *Config) error {
	if path == "" {
		path = ConfigPath()
	}

	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("creating config directory: %w", err)
	}

	data, err := yaml.Marshal(cfg)
	if err != nil {
		return fmt.Errorf("marshaling config: %w", err)
	}

	if err := os.WriteFile(path, data, 0644); err != nil {
		return fmt.Errorf("writing config: %w", err)
	}

	return nil
}

func (c *Config) applyDefaults() {
	if c.OrchestratorURL == "" {
		c.OrchestratorURL = DefaultConfig.OrchestratorURL
	}
	if c.ScannerURL == "" {
		c.ScannerURL = DefaultConfig.ScannerURL
	}
	if c.ExploitURL == "" {
		c.ExploitURL = DefaultConfig.ExploitURL
	}
	if c.ReporterURL == "" {
		c.ReporterURL = DefaultConfig.ReporterURL
	}
}

func (c *Config) merge(other *Config) {
	if other.OrchestratorURL != "" {
		c.OrchestratorURL = other.OrchestratorURL
	}
	if other.ScannerURL != "" {
		c.ScannerURL = other.ScannerURL
	}
	if other.ExploitURL != "" {
		c.ExploitURL = other.ExploitURL
	}
	if other.ReporterURL != "" {
		c.ReporterURL = other.ReporterURL
	}
	if other.NotifierURL != "" {
		c.NotifierURL = other.NotifierURL
	}
	if other.SourceURL != "" {
		c.SourceURL = other.SourceURL
	}
	if other.ImmunefiURL != "" {
		c.ImmunefiURL = other.ImmunefiURL
	}
	if other.ProjectDir != "" {
		c.ProjectDir = other.ProjectDir
	}
	if other.OutputFormat != "" {
		c.OutputFormat = other.OutputFormat
	}
	if other.OpenAIKey != "" {
		c.OpenAIKey = other.OpenAIKey
	}
	if other.AnthropicKey != "" {
		c.AnthropicKey = other.AnthropicKey
	}
	if other.DeepseekKey != "" {
		c.DeepseekKey = other.DeepseekKey
	}
}
