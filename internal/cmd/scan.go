package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
)

// scanCmd represents the scan command.
var scanCmd = &cobra.Command{
	Use:   "scan [file]",
	Short: "Quick scan a Solidity contract file",
	Long:  `Run static analysis tools (Slither, Mythril, Echidna) on a local Solidity file.`,
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		file := args[0]
		tools, _ := cmd.Flags().GetStringSlice("tools")
		compiler, _ := cmd.Flags().GetString("compiler")

		fmt.Printf("Scanning %s with tools=%v (compiler: %s)\n", file, tools, compiler)
		// TODO: Implement via client.Client
		return nil
	},
}

func init() {
	rootCmd.AddCommand(scanCmd)

	scanCmd.Flags().StringSliceP("tools", "t", []string{"slither", "mythril", "echidna"}, "Tools to use")
	scanCmd.Flags().StringP("compiler", "c", "0.8.20", "Solidity compiler version")
}
