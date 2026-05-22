package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
)

// healthCmd represents the health command.
var healthCmd = &cobra.Command{
	Use:   "health",
	Short: "Check all service health status",
	RunE: func(cmd *cobra.Command, args []string) error {
		fmt.Println("Checking all service health...")
		// TODO: Implement via client.Client
		return nil
	},
}

func init() {
	rootCmd.AddCommand(healthCmd)
}
