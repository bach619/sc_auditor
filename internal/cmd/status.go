package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
)

// statusCmd represents the status command.
var statusCmd = &cobra.Command{
	Use:   "status [audit-id]",
	Short: "Check audit status",
	Long:  `Get the current status and results of an audit by its ID.`,
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		auditID := args[0]
		fmt.Printf("Fetching status for audit %s\n", auditID)
		// TODO: Implement via client.Client
		return nil
	},
}

// listCmd represents the list command.
var listCmd = &cobra.Command{
	Use:   "list",
	Short: "List all audits",
	RunE: func(cmd *cobra.Command, args []string) error {
		state, _ := cmd.Flags().GetString("state")
		limit, _ := cmd.Flags().GetInt("limit")

		fmt.Printf("Listing audits (state=%s, limit=%d)\n", state, limit)
		// TODO: Implement via client.Client
		return nil
	},
}

// statsCmd represents the stats command.
var statsCmd = &cobra.Command{
	Use:   "stats",
	Short: "Show pipeline statistics",
	RunE: func(cmd *cobra.Command, args []string) error {
		fmt.Println("Fetching pipeline statistics...")
		// TODO: Implement via client.Client
		return nil
	},
}

// queueCmd represents the queue command.
var queueCmd = &cobra.Command{
	Use:   "queue",
	Short: "View the audit priority queue",
	RunE: func(cmd *cobra.Command, args []string) error {
		fmt.Println("Fetching priority queue...")
		// TODO: Implement via client.Client
		return nil
	},
}

func init() {
	rootCmd.AddCommand(statusCmd)
	rootCmd.AddCommand(listCmd)
	rootCmd.AddCommand(statsCmd)
	rootCmd.AddCommand(queueCmd)

	listCmd.Flags().StringP("state", "s", "", "Filter by state (completed, pending, failed)")
	listCmd.Flags().IntP("limit", "l", 50, "Maximum number of results")
}
