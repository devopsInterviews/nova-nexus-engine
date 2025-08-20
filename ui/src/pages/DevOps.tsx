import { ThemedTabs, ThemedTabsList, ThemedTabsTrigger, ThemedTabsContent } from "@/components/ui/themed-tabs";
import { JenkinsTab } from "@/components/devops/JenkinsTab";
import { LogsTab } from "@/components/devops/LogsTab";
import { BitbucketTab } from "@/components/devops/BitbucketTab";
import { JiraTab } from "@/components/devops/JiraTab";
import { motion } from "framer-motion";

export default function DevOps() {
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
        <h1 className="text-3xl font-bold gradient-text mb-2">DevOps Control Center</h1>
        <p className="text-muted-foreground">
          Unified access to Jenkins, Elasticsearch logs, Bitbucket repositories, and Jira tickets
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <ThemedTabs defaultValue="jenkins" className="w-full">
          <ThemedTabsList className="grid w-full grid-cols-4">
            <ThemedTabsTrigger value="jenkins" layoutId="devopsTab">Jenkins</ThemedTabsTrigger>
            <ThemedTabsTrigger value="logs" layoutId="devopsTab">Logs</ThemedTabsTrigger>
            <ThemedTabsTrigger value="bitbucket" layoutId="devopsTab">Bitbucket</ThemedTabsTrigger>
            <ThemedTabsTrigger value="jira" layoutId="devopsTab">Jira</ThemedTabsTrigger>
          </ThemedTabsList>

          <ThemedTabsContent value="jenkins">
            <JenkinsTab />
          </ThemedTabsContent>

          <ThemedTabsContent value="logs">
            <LogsTab />
          </ThemedTabsContent>

          <ThemedTabsContent value="bitbucket">
            <BitbucketTab />
          </ThemedTabsContent>

          <ThemedTabsContent value="jira">
            <JiraTab />
          </ThemedTabsContent>
        </ThemedTabs>
      </motion.div>
    </motion.div>
  );
}