# DP 解题 Skill

## 五步流程
1. **定状态**：找到"阶段"和"需要记录的信息"→ 定义 `dp[i][...]` 的含义
2. **找转移**：当前状态由哪些子状态推出，写出递推方程
3. **定初始**：最小子问题的值（base case）
4. **定顺序**：确保算 `dp[i]` 时所依赖的状态已算完
5. **定答案**：目标在 `dp[n]` 还是 `max/min(dp[...])` 中

---

## 常见模式模板

### 1. 线性 DP
**LIS:** `dp[i]` = 以 `a[i]` 结尾的最长递增子序列长度
```
dp[i] = max(dp[j] + 1) for j < i and a[j] < a[i]
```
**LCS:** `dp[i][j]` = `a[0..i]` 与 `b[0..j]` 的最长公共子序列
```
dp[i][j] = dp[i-1][j-1]+1 if a[i]==b[j] else max(dp[i-1][j], dp[i][j-1])
```

### 2. 背包 DP
**0-1背包:** `dp[j]` = 容量 `j` 下最大价值
```
for i in items: for j in W..w[i]: dp[j] = max(dp[j], dp[j-w[i]]+v[i])
```
**完全背包:** 内层正序
```
for i in items: for j in w[i]..W: dp[j] = max(dp[j], dp[j-w[i]]+v[i])
```

### 3. 区间 DP
`dp[i][j]` = 区间 `[i,j]` 的最优解
```
for len in 2..n: for i in 0..n-len: j=i+len-1:
  dp[i][j] = min/max(dp[i][k] + dp[k+1][j] + cost(i,k,j)) for k in i..j-1
```

### 4. 树形 DP
`dp[u][...]` = 以 `u` 为根的子树的最优解，DFS 后序处理
```
def dfs(u):
  for v in children(u):
    dfs(v)
    dp[u][j] = opt(dp[u][j], dp[v][k] + ...) // 合并子树
```

### 5. 状态机 DP
`dp[i][state]` = 第 `i` 步处于 `state` 的最优值
```
// 例: 买卖股票 hold/empty
dp[i][hold] = max(dp[i-1][hold], dp[i-1][empty] - price[i])
dp[i][empty] = max(dp[i-1][empty], dp[i-1][hold] + price[i])
```

---

## 速判技巧
- 最优/计数/可行性 → 大概率 DP
- 有"选/不选" → 背包/子序列
- 连续区间合并 → 区间 DP
- 树上选择 → 树形 DP
- 多阶段状态切换 → 状态机 DP