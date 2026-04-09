# DP 解题 Skill

## 五步流程

1. **定状态**：找到"最后一步"的决策，确定 `dp[i]` 或 `dp[i][j]` 的含义
2. **推转移**：从子问题推当前问题，写出递推方程
3. **定初始**：最小子问题的边界值
4. **定顺序**：保证计算当前状态时，所依赖的状态已算完
5. **定答案**：目标在 `dp[n]`、`dp[n][m]`、还是 `max(dp[*])`

---

## 模式模板

### 线性DP
**状态**：`dp[i]` = 考虑前 i 个元素的最优值
```
dp[i] = max/min(dp[j] + cost(j,i))  for valid j < i
```
LIS变体：`dp[i]` = 以 `a[i]` 结尾的最长子序列，`dp[i] = max(dp[j]+1) for j<i and a[j]<a[i]`

### 区间DP
**状态**：`dp[i][j]` = 区间 `[i,j]` 的最优值
```
for len in 2..n:
  for i in 0..n-len:
    j = i+len-1
    dp[i][j] = min/max(dp[i][k] + dp[k+1][j] + cost(i,j)) for k in [i,j)
```

### 背包DP
**0-1背包**：`dp[j]` = 容量 j 下的最大价值
```
for i in 0..n:
  for j in W..w[i] (倒序):
    dp[j] = max(dp[j], dp[j-w[i]] + v[i])
```
**完全背包**：内层改正序。**多重背包**：二进制拆分转0-1。

### 树形DP
**状态**：`dp[u][...]` = 以 u 为根的子树的最优值
```
def dfs(u, parent):
  dp[u][0/1] = base
  for v in children(u):
    dfs(v, u)
    dp[u][1] += min(dp[v][0], dp[v][1])   # 例：最小覆盖
    dp[u][0] += dp[v][1]
```

### 状态机DP
**状态**：`dp[i][state]`，`state` 编码当前所处的阶段/状态
```
# 例：买卖股票含冷冻期，state∈{持有, 不持有, 冷冻}
dp[i][hold]   = max(dp[i-1][hold], dp[i-1][cool] - price[i])
dp[i][empty]  = max(dp[i-1][empty], dp[i-1][hold] + price[i])
dp[i][cool]   = dp[i-1][empty]
```

---

## 速查口诀

| 信号 | 模式 |
|---|---|
| 序列+最优子结构 | 线性DP |
| 合并/消除区间 | 区间DP |
| 容量+选择 | 背包DP |
| 树/图+子树信息 | 树形DP |
| 阶段间有约束/模式切换 | 状态机DP |

**优化意识**：单调栈/队列优化线性DP；前缀和优化区间求值；滚动数组/状态压缩降维。