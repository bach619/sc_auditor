package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
)

// auditCmd represents the audit command.
var auditCmd = &cobra.Command{
	Use:   "audit [address]",
	Short: "Start a full audit pipeline for a contract address",
	Long:  `Submit a smart contract address for a full audit pipeline: fetch source, scan, analyze, exploit, and report.`,
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		address := args[0]
		chain, _ := cmd.Flags().GetString("chain")
		program, _ := cmd.Flags().GetString("program")
		priority, _ := cmd.Flags().GetInt("priority")

		fmt.Printf("Starting audit for contract %s on %s (priority: %d)\n", address, chain, priority)
		_ = program
		// TODO: Implement via client.Client
		return nil
	},
}

func init() {
	rootCmd.AddCommand(auditCmd)

	auditCmd.Flags().StringP("chain", "c", "ethereum", "Blockchain network (ethereum, bsc, polygon, etc.)")
	auditCmd.Flags().StringP("program", "p", "", "Bug bounty program name")
	auditCmd.Flags().IntP("priority", "r", 5, "Audit priority (1-10)")
}
