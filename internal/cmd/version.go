package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
)

var Version = "0.1.0"

// versionCmd represents the version command.
var versionCmd = &cobra.Command{
	Use:   "version",
	Short: "Show the Vyper CLI version",
	Run: func(cmd *cobra.Command, args []string) {
		fmt.Printf("Vyper CLI v%s\n", Version)
		fmt.Println("Smart Contract Bug Hunter")
	},
}

func init() {
	rootCmd.AddCommand(versionCmd)
}
