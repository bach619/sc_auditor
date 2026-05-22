package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
)

// configCmd represents the config command.
var configCmd = &cobra.Command{
	Use:   "config",
	Short: "Show or edit configuration",
	RunE: func(cmd *cobra.Command, args []string) error {
		show, _ := cmd.Flags().GetBool("show")
		key, _ := cmd.Flags().GetString("set")

		if show {
			fmt.Println("Current configuration:")
			// TODO: Show config
		} else if key != "" {
			value, _ := cmd.Flags().GetString("value")
			fmt.Printf("Setting %s = %s\n", key, value)
			// TODO: Set config
		} else {
			fmt.Println("Use --show to view config, --set to update")
		}
		return nil
	},
}

func init() {
	rootCmd.AddCommand(configCmd)

	configCmd.Flags().BoolP("show", "s", false, "Show current configuration")
	configCmd.Flags().StringP("set", "k", "", "Configuration key to set")
	configCmd.Flags().StringP("value", "v", "", "Configuration value")
}
