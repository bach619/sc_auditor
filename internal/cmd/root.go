package cmd

import (
	"os"

	"github.com/spf13/cobra"
)

var cfgFile string

// rootCmd represents the base command when called without any subcommands.
var rootCmd = &cobra.Command{
	Use:   "vyper",
	Short: "Smart Contract Bug Hunter — analyze, exploit, and report on Solidity contracts",
	Long: `Vyper is a microservice-based smart contract bug hunting platform.

It scans Solidity contracts using multiple tools (Slither, Mythril, Echidna, Halmos, Forge),
analyzes findings with AI, generates PoC exploits, and produces professional audit reports.`,
}

// Execute adds all child commands to the root command and sets flags appropriately.
// This is called by main.main(). It only needs to happen once.
func Execute() {
	err := rootCmd.Execute()
	if err != nil {
		os.Exit(1)
	}
}

func init() {
	cobra.OnInitialize(initConfig)

	// Global flags
	rootCmd.PersistentFlags().StringVar(&cfgFile, "config", "", "config file (default $HOME/.vyper/config.yml)")
	rootCmd.PersistentFlags().StringP("format", "f", "auto", "output format: auto, json, text")
	rootCmd.PersistentFlags().BoolP("debug", "d", false, "enable debug logging")
}

func initConfig() {
	// Config loading will be implemented in internal/config
}
