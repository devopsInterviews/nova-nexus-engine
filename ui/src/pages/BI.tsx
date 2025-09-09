import { ThemedTabs, ThemedTabsList, ThemedTabsTrigger, ThemedTabsContent } from "@/components/ui/themed-tabs";
import { ConnectDBTab } from "@/components/bi/ConnectDBTab";
import { ColumnSuggestionsTab } from "@/components/bi/ColumnSuggestionsTab";
import { SQLBuilderTab } from "@/components/bi/SQLBuilderTab";
import { SqlBuilderDbtTab } from "@/components/bi/SqlBuilderDbtTab";
import { SyncTablesTab } from "@/components/bi/SyncTablesTab";
import { motion } from "framer-motion";

export default function BI() {
  return (
    <motion.div 
      className="space-y-6"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.6 }}
    >
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <h1 className="text-3xl font-bold gradient-text mb-2">Business Intelligence Hub</h1>
        <p className="text-muted-foreground">
          Connect to databases, analyze data with AI, and sync documentation automatically
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <ThemedTabs defaultValue="connect" className="w-full">
          <ThemedTabsList className="grid w-full grid-cols-5">
            <ThemedTabsTrigger value="connect" layoutId="biTab">Connect to DB</ThemedTabsTrigger>
            <ThemedTabsTrigger value="suggestions" layoutId="biTab">Column Suggestions</ThemedTabsTrigger>
            <ThemedTabsTrigger value="sql" layoutId="biTab">SQL Builder</ThemedTabsTrigger>
            <ThemedTabsTrigger value="dbt" layoutId="biTab">SQL Builder - dbt</ThemedTabsTrigger>
            <ThemedTabsTrigger value="sync" layoutId="biTab">Sync Tables to Confluence</ThemedTabsTrigger>
          </ThemedTabsList>

          <ThemedTabsContent value="connect">
            <ConnectDBTab />
          </ThemedTabsContent>

          <ThemedTabsContent value="suggestions">
            <ColumnSuggestionsTab />
          </ThemedTabsContent>

          <ThemedTabsContent value="sql">
            <SQLBuilderTab />
          </ThemedTabsContent>

          <ThemedTabsContent value="dbt">
            <SqlBuilderDbtTab />
          </ThemedTabsContent>

          <ThemedTabsContent value="sync">
            <SyncTablesTab />
          </ThemedTabsContent>
        </ThemedTabs>
      </motion.div>
    </motion.div>
  );
}