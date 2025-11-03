# QuantLab Repository Setup & Git Workflow Guide

## 🏗️ Repository Architecture (Updated Oct 2025)

### **Current Setup:**
- **Local Development**: `/Users/abhishekshah/Desktop/quantlab-workspace`
- **GitHub Repository**: `https://github.com/abhishekjs0/quantlab-bot.git`
- **Repository State**: Unified, complete system with all features

### **Important Changes Made:**
1. **✅ Unified Repository**: Consolidated all content into `quantlab-bot`
2. **✅ Local Rename**: `quantlab` → `quantlab-workspace` (eliminates confusion)
3. **✅ Complete Content**: All reports, dashboards, and features included
4. **✅ Clean Git History**: Resolved divergence and sync issues

## 🔄 Git Workflow Understanding

### **How Git Commit & Push Works:**

```bash
# 1. Stage files (prepare for commit)
git add .                    # Stages all changed files
git add filename.py          # Stages specific file

# 2. Commit to LOCAL repository
git commit -m "Your message" # Saves changes LOCALLY only

# 3. Push to GitHub repository  
git push origin main         # Uploads commits to GitHub

# 4. Check status anytime
git status                   # Shows what needs commit/push
```

### **Key Understanding:**
- **📝 Edit files** → Changes saved to disk immediately
- **📦 `git commit`** → Saves changes to LOCAL git history
- **🌐 `git push`** → Syncs LOCAL commits to GitHub
- **✅ Both updated** → Your local files AND GitHub are in sync after push

### **Visual Flow:**
```
Your Files → git add → git commit → LOCAL REPO
                                        ↓
                               git push → GITHUB REPO
```

## 🔧 Repository Maintenance Workflow

### **Daily Development:**
```bash
cd /Users/abhishekshah/Desktop/quantlab-workspace

# Check current status
git status

# Stage and commit changes
git add .
git commit -m "feat: describe your changes"

# Push to quantlab-bot repository
git push origin main
```

### **Repository Verification:**
```bash
# Verify you're in the right place
pwd                          # Should show: .../quantlab-workspace
git remote -v               # Should show: quantlab-bot.git
git branch                  # Should show: * main
```

## 📚 Documentation Integration

### **Key Files Updated:**
- ✅ `run_janitor.sh` → All references point to quantlab-bot
- ✅ `REPO_JANITOR_ENHANCED.md` → Enhanced git issue handling  
- ✅ All deployment scripts → Target quantlab-bot repository
- ✅ Documentation → Consistent repository references

### **Repository URLs:**
- **GitHub**: https://github.com/abhishekjs0/quantlab-bot.git
- **Local**: /Users/abhishekshah/Desktop/quantlab-workspace
- **Clone Command**: `git clone https://github.com/abhishekjs0/quantlab-bot.git`

## ⚠️ Important Notes

### **What Was Fixed:**
1. **Git-LFS Issues**: Removed problematic configuration
2. **Repository Divergence**: Synced local with complete remote
3. **Naming Confusion**: Clear distinction between local/remote
4. **Missing Content**: All reports and dashboards now tracked

### **Best Practices:**
- ✅ Always work in `quantlab-workspace` directory
- ✅ Commit frequently with descriptive messages
- ✅ Push regularly to keep GitHub updated
- ✅ Use `git status` to check sync state
- ✅ Run janitor script for maintenance

## 🚀 Quick Start Commands

```bash
# Navigate to workspace
cd /Users/abhishekshah/Desktop/quantlab-workspace

# Daily workflow
git status                   # Check current state
git add .                   # Stage all changes  
git commit -m "your message" # Commit locally
git push origin main        # Push to GitHub

# Maintenance
./run_janitor.sh            # Run repository maintenance
```

This setup ensures your QuantLab system is properly managed with clear naming, unified content, and reliable git workflows! ��
