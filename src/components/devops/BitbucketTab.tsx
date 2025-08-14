import { ThemedTabs, ThemedTabsList, ThemedTabsTrigger, ThemedTabsContent } from "@/components/ui/themed-tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { motion } from "framer-motion";
import { GitBranch, Folder, File, MessageSquare, GitPullRequest, Play, Users } from "lucide-react";

export function BitbucketTab() {
  const repositories = [
    { name: "frontend-app", branches: 8, lastCommit: "2 hours ago", language: "TypeScript" },
    { name: "backend-api", branches: 12, lastCommit: "30 min ago", language: "Python" },
    { name: "mobile-app", branches: 6, lastCommit: "1 day ago", language: "React Native" },
    { name: "infrastructure", branches: 3, lastCommit: "3 hours ago", language: "Terraform" },
  ];

  const pullRequests = [
    { 
      title: "Feature: Add user authentication", 
      author: "john.doe", 
      status: "open", 
      comments: 3,
      created: "2 days ago",
      reviewers: ["jane.smith", "mike.wilson"]
    },
    { 
      title: "Fix: Database connection timeout", 
      author: "jane.smith", 
      status: "approved", 
      comments: 7,
      created: "1 day ago",
      reviewers: ["john.doe"]
    },
    { 
      title: "Refactor: Update API endpoints", 
      author: "mike.wilson", 
      status: "changes-requested", 
      comments: 12,
      created: "3 days ago",
      reviewers: ["john.doe", "jane.smith"]
    },
  ];

  const files = [
    { name: "src/", type: "folder", modified: "2 hours ago" },
    { name: "package.json", type: "file", modified: "1 day ago", size: "2.1 KB" },
    { name: "README.md", type: "file", modified: "3 days ago", size: "4.5 KB" },
    { name: "tsconfig.json", type: "file", modified: "1 week ago", size: "890 B" },
    { name: ".gitignore", type: "file", modified: "2 weeks ago", size: "1.2 KB" },
  ];

  const statusColors = {
    open: "bg-primary/10 text-primary border-primary/20",
    approved: "bg-success/10 text-success border-success/20",
    "changes-requested": "bg-warning/10 text-warning border-warning/20",
    merged: "bg-secondary/10 text-secondary border-secondary/20",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <ThemedTabs defaultValue="files" className="w-full">
        <ThemedTabsList className="grid w-full grid-cols-3">
          <ThemedTabsTrigger value="files">List Files</ThemedTabsTrigger>
          <ThemedTabsTrigger value="pr-comment">Comment on PR</ThemedTabsTrigger>
          <ThemedTabsTrigger value="pr-sync">PR Sync Runner</ThemedTabsTrigger>
        </ThemedTabsList>

        <ThemedTabsContent value="files">
          <div className="space-y-6">
            {/* Repository Selector */}
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
            >
              <Card className="glass border-border/50">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <GitBranch className="w-5 h-5 text-primary" />
                    Repository Browser
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Repository</label>
                      <Select>
                        <SelectTrigger className="bg-surface-elevated">
                          <SelectValue placeholder="Select repository" />
                        </SelectTrigger>
                        <SelectContent>
                          {repositories.map((repo) => (
                            <SelectItem key={repo.name} value={repo.name}>
                              {repo.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Branch</label>
                      <Select>
                        <SelectTrigger className="bg-surface-elevated">
                          <SelectValue placeholder="main" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="main">main</SelectItem>
                          <SelectItem value="develop">develop</SelectItem>
                          <SelectItem value="feature/auth">feature/auth</SelectItem>
                          <SelectItem value="hotfix/critical">hotfix/critical</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Path</label>
                      <Input placeholder="/" className="bg-surface-elevated" />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>

            {/* File Browser */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
            >
              <Card className="glass border-border/50">
                <CardHeader>
                  <CardTitle>Files & Folders</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {files.map((file, index) => (
                      <motion.div
                        key={file.name}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.5 + index * 0.1 }}
                        className="flex items-center justify-between p-3 rounded-lg bg-surface-elevated/50 hover:bg-surface-elevated transition-colors group cursor-pointer"
                      >
                        <div className="flex items-center gap-3">
                          {file.type === "folder" ? (
                            <Folder className="w-5 h-5 text-primary" />
                          ) : (
                            <File className="w-5 h-5 text-muted-foreground" />
                          )}
                          <div>
                            <h4 className="font-medium group-hover:text-primary transition-colors">{file.name}</h4>
                            <p className="text-sm text-muted-foreground">
                              Modified {file.modified}
                              {file.size && ` • ${file.size}`}
                            </p>
                          </div>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </motion.div>

            {/* Repositories Grid */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 }}
            >
              <Card className="glass border-border/50">
                <CardHeader>
                  <CardTitle>All Repositories</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {repositories.map((repo, index) => (
                      <motion.div
                        key={repo.name}
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: 0.7 + index * 0.1 }}
                        className="p-4 rounded-lg glass border-border/50 hover:shadow-glow transition-all duration-smooth group"
                      >
                        <div className="flex items-center justify-between mb-3">
                          <h4 className="font-medium group-hover:text-primary transition-colors">{repo.name}</h4>
                          <Badge variant="outline" className="text-xs">{repo.language}</Badge>
                        </div>
                        
                        <div className="space-y-2 text-sm text-muted-foreground">
                          <div className="flex justify-between">
                            <span>Branches:</span>
                            <span className="text-foreground">{repo.branches}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Last commit:</span>
                            <span className="text-foreground">{repo.lastCommit}</span>
                          </div>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          </div>
        </ThemedTabsContent>

        <ThemedTabsContent value="pr-comment">
          <div className="space-y-6">
            {/* PR Selector */}
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
            >
              <Card className="glass border-border/50">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <MessageSquare className="w-5 h-5 text-primary" />
                    Comment on Pull Request
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Repository</label>
                      <Select>
                        <SelectTrigger className="bg-surface-elevated">
                          <SelectValue placeholder="Select repository" />
                        </SelectTrigger>
                        <SelectContent>
                          {repositories.map((repo) => (
                            <SelectItem key={repo.name} value={repo.name}>
                              {repo.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Pull Request</label>
                      <Select>
                        <SelectTrigger className="bg-surface-elevated">
                          <SelectValue placeholder="Select PR" />
                        </SelectTrigger>
                        <SelectContent>
                          {pullRequests.map((pr, index) => (
                            <SelectItem key={index} value={index.toString()}>
                              #{index + 1} {pr.title}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Comment</label>
                    <Textarea 
                      placeholder="Add your comment here..."
                      className="bg-surface-elevated"
                      rows={4}
                    />
                  </div>
                  
                  <Button className="bg-gradient-primary">
                    <MessageSquare className="w-4 h-4 mr-2" />
                    Post Comment
                  </Button>
                </CardContent>
              </Card>
            </motion.div>

            {/* Pull Requests List */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
            >
              <Card className="glass border-border/50">
                <CardHeader>
                  <CardTitle>Active Pull Requests</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {pullRequests.map((pr, index) => (
                      <motion.div
                        key={index}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.5 + index * 0.1 }}
                        className="p-4 rounded-lg bg-surface-elevated/50 hover:bg-surface-elevated transition-colors group"
                      >
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex-1">
                            <h4 className="font-medium group-hover:text-primary transition-colors mb-1">
                              {pr.title}
                            </h4>
                            <div className="flex items-center gap-4 text-sm text-muted-foreground">
                              <span>by {pr.author}</span>
                              <span>{pr.created}</span>
                              <div className="flex items-center gap-1">
                                <MessageSquare className="w-4 h-4" />
                                {pr.comments}
                              </div>
                            </div>
                          </div>
                          
                          <Badge variant="outline" className={statusColors[pr.status as keyof typeof statusColors]}>
                            {pr.status.replace("-", " ")}
                          </Badge>
                        </div>
                        
                        <div className="flex items-center gap-2">
                          <Users className="w-4 h-4 text-muted-foreground" />
                          <span className="text-sm text-muted-foreground">
                            Reviewers: {pr.reviewers.join(", ")}
                          </span>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          </div>
        </ThemedTabsContent>

        <ThemedTabsContent value="pr-sync">
          <Card className="glass border-border/50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Play className="w-5 h-5 text-primary" />
                PR Sync Runner
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Source Repository</label>
                  <Select>
                    <SelectTrigger className="bg-surface-elevated">
                      <SelectValue placeholder="Select source repo" />
                    </SelectTrigger>
                    <SelectContent>
                      {repositories.map((repo) => (
                        <SelectItem key={repo.name} value={repo.name}>
                          {repo.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Target Repository</label>
                  <Select>
                    <SelectTrigger className="bg-surface-elevated">
                      <SelectValue placeholder="Select target repo" />
                    </SelectTrigger>
                    <SelectContent>
                      {repositories.map((repo) => (
                        <SelectItem key={repo.name} value={repo.name}>
                          {repo.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Sync Configuration</label>
                <Textarea 
                  placeholder="Enter sync rules and filters..."
                  className="bg-surface-elevated"
                  rows={6}
                />
              </div>
              
              <Button className="bg-gradient-primary">
                <Play className="w-4 h-4 mr-2" />
                Start Sync Process
              </Button>
              
              <div className="bg-surface-elevated rounded-lg p-6 border border-border/50">
                <h4 className="font-medium mb-3 text-primary">Sync Status</h4>
                <div className="space-y-2 text-muted-foreground">
                  <p>• Last sync: 2 hours ago</p>
                  <p>• Status: Completed successfully</p>
                  <p>• PRs synchronized: 15</p>
                  <p>• Next scheduled sync: in 6 hours</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </ThemedTabsContent>
      </ThemedTabs>
    </motion.div>
  );
}