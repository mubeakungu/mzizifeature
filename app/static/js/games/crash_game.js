/**
 * mzizicrash - Real-Time Multiplier Chart Game
 * 
 * Features:
 * - Real-time Chart.js visualization of crash curve
 * - Unpredictable crash points (2x to 500x)
 * - WebSocket integration for multiplayer
 * - Auto-cashout support
 * - Live metrics and statistics
 */

// ============================================================================
// GAME STATE
// ============================================================================

const gameState = {
  roundNumber: 0,
  status: 'waiting', // waiting, betting, live, crashed
  currentMultiplier: 1.00,
  crashPoint: null,
  playerBetId: null,
  playerBetAmount: 0,
  playerStatus: 'idle', // idle, betting, active, cashed_out, lost
  autoCashoutMultiplier: null,
  
  chartData: [],
  chartLabels: [],
  
  stats: {
    totalWagered: 0,
    totalWon: 0,
    wins: 0,
    losses: 0,
    bestMultiplier: 0,
  },
  
  recentBets: [],
};

// ============================================================================
// CHART SETUP
// ============================================================================

let chart = null;

function initChart() {
  const ctx = document.getElementById('crash-chart').getContext('2d');
  
  chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: gameState.chartLabels,
      datasets: [
        {
          label: 'Multiplier',
          data: gameState.chartData,
          borderColor: '#0ea5e9',
          backgroundColor: 'rgba(14, 165, 233, 0.1)',
          borderWidth: 3,
          fill: true,
          tension: 0.4,
          pointRadius: 0,
          pointHoverRadius: 0,
          segment: {
            borderColor: ctx => ctx.p0DataIndex === gameState.chartData.length - 1 
              ? '#ef4444' 
              : '#0ea5e9'
          }
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          titleColor: '#fff',
          bodyColor: '#fff',
          borderColor: '#0ea5e9',
          borderWidth: 1,
          padding: 12,
          callbacks: {
            label: function(context) {
              return `Multiplier: ${context.parsed.y.toFixed(2)}x`;
            }
          }
        }
      },
      scales: {
        x: {
          display: false,
          grid: { display: false }
        },
        y: {
          beginAtZero: true,
          min: 0.9,
          max: 100,
          type: 'logarithmic',
          grid: {
            color: 'rgba(255, 255, 255, 0.1)',
            drawBorder: false
          },
          ticks: {
            color: 'rgba(255, 255, 255, 0.5)',
            font: { size: 11 },
            callback: function(value) {
              if (value === 1) return '1.0x';
              if (value === 10) return '10x';
              if (value === 100) return '100x';
              return value.toFixed(0) + 'x';
            }
          }
        }
      }
    }
  });
}

function resetChart() {
  gameState.chartData = [];
  gameState.chartLabels = [];
  
  if (chart) {
    chart.data.labels = gameState.chartLabels;
    chart.data.datasets[0].data = gameState.chartData;
    chart.update('none'); // No animation on reset
  }
}

function updateChart(multiplier, elapsed) {
  gameState.chartData.push(multiplier);
  gameState.chartLabels.push((elapsed).toFixed(1));
  
  // Keep last 500 data points for performance
  if (gameState.chartData.length > 500) {
    gameState.chartData.shift();
    gameState.chartLabels.shift();
  }
  
  if (chart) {
    chart.data.labels = gameState.chartLabels;
    chart.data.datasets[0].data = gameState.chartData;
    chart.update('none'); // No animation, just update
  }
}

// ============================================================================
// DOM UPDATES
// ============================================================================

function updateUI() {
  document.getElementById('current-multiplier').textContent = 
    gameState.currentMultiplier.toFixed(2) + 'x';
  
  document.getElementById('round-number').textContent = gameState.roundNumber;
  
  const statusEl = document.getElementById('status-text');
  statusEl.className = 'status-label ' + gameState.status;
  
  switch (gameState.status) {
    case 'betting':
      statusEl.textContent = '🎰 Place your bet...';
      break;
    case 'live':
      statusEl.textContent = '🚀 Game is LIVE - Cash out anytime!';
      break;
    case 'crashed':
      statusEl.textContent = `💥 Crashed at ${gameState.crashPoint.toFixed(2)}x`;
      break;
    default:
      statusEl.textContent = 'Waiting for next round...';
  }
  
  // Update button states
  const betBtn = document.getElementById('bet-button');
  const cashoutBtn = document.getElementById('cashout-button');
  
  if (gameState.status === 'betting' && gameState.playerStatus === 'idle') {
    betBtn.disabled = false;
    betBtn.style.display = 'block';
    cashoutBtn.style.display = 'none';
  } else if (gameState.status === 'live' && gameState.playerStatus === 'active') {
    betBtn.disabled = true;
    betBtn.style.display = 'none';
    cashoutBtn.style.display = 'block';
  } else {
    betBtn.disabled = true;
    betBtn.style.display = 'block';
    cashoutBtn.style.display = 'none';
  }
}

function updateBalance(balance) {
  document.getElementById('balance').textContent = formatMoney(balance);
}

function updateStats() {
  document.getElementById('stat-total-wagered').textContent = 
    formatMoney(gameState.stats.totalWagered);
  document.getElementById('stat-total-won').textContent = 
    formatMoney(gameState.stats.totalWon);
  document.getElementById('stat-wins').textContent = gameState.stats.wins;
  document.getElementById('stat-losses').textContent = gameState.stats.losses;
  document.getElementById('stat-best-multiplier').textContent = 
    gameState.stats.bestMultiplier > 0 
      ? gameState.stats.bestMultiplier.toFixed(2) + 'x' 
      : '-';
}

function updateRecentBets() {
  const container = document.getElementById('recent-bets');
  
  if (gameState.recentBets.length === 0) {
    container.innerHTML = '<p class="empty-state">No bets yet</p>';
    return;
  }
  
  container.innerHTML = gameState.recentBets.slice(0, 10).map(bet => `
    <div class="bet-item ${bet.status}">
      <span class="label">Bet ${bet.amount} KES</span>
      <span class="value">${bet.payout ? '+' + formatMoney(bet.payout) : 'Lost'}</span>
    </div>
  `).join('');
}

function formatMoney(amount) {
  return new Intl.NumberFormat('en-KE', {
    style: 'currency',
    currency: 'KES',
    minimumFractionDigits: 0
  }).format(amount);
}

// ============================================================================
// SOCKET.IO EVENTS
// ============================================================================

const socket = io('/crash');

socket.on('connect', () => {
  console.log('Connected to mzizicrash');
  socket.emit('join_game');
  socket.emit('request_current_state');
});

socket.on('new_round', (data) => {
  console.log('New round:', data.round_number);
  gameState.roundNumber = data.round_number;
  gameState.status = 'betting';
  gameState.playerStatus = 'idle';
  gameState.playerBetId = null;
  gameState.playerBetAmount = 0;
  gameState.autoCashoutMultiplier = parseFloat(
    document.getElementById('auto-cashout-multiplier').value
  ) || null;
  
  resetChart();
  updateUI();
});

socket.on('game_start', (data) => {
  console.log('Game started');
  gameState.status = 'live';
  gameState.currentMultiplier = 1.00;
  
  updateUI();
});

socket.on('multiplier_update', (data) => {
  gameState.currentMultiplier = data.multiplier;
  
  updateChart(data.multiplier, data.elapsed);
  updateUI();
  
  // Auto-cashout check
  if (gameState.playerStatus === 'active' && gameState.autoCashoutMultiplier) {
    if (data.multiplier >= gameState.autoCashoutMultiplier) {
      console.log('Auto-cashout triggered at', data.multiplier);
      cashout();
    }
  }
});

socket.on('game_crashed', (data) => {
  console.log('Game crashed at', data.crash_point);
  gameState.status = 'crashed';
  gameState.crashPoint = data.crash_point;
  gameState.currentMultiplier = data.crash_point;
  
  // Mark player as lost if still active
  if (gameState.playerStatus === 'active') {
    gameState.playerStatus = 'lost';
    gameState.stats.losses++;
  }
  
  updateUI();
  updateStats();
  
  // Fetch stats after crash
  setTimeout(() => {
    fetch('/crash/api/stats')
      .then(r => r.json())
      .then(stats => {
        gameState.stats.totalWagered = stats.total_wagered;
        gameState.stats.totalWon = stats.total_won;
        gameState.stats.bestMultiplier = stats.best_multiplier || 0;
        updateStats();
      });
    
    fetch('/crash/api/history?limit=10')
      .then(r => r.json())
      .then(bets => {
        gameState.recentBets = bets.map(b => ({
          amount: b.amount,
          payout: b.payout,
          status: b.status,
          multiplier: b.cashout_at || b.crash_point
        }));
        updateRecentBets();
      });
  }, 500);
});

socket.on('player_joined', (data) => {
  document.getElementById('player-count').textContent = data.players;
});

socket.on('current_state', (data) => {
  gameState.roundNumber = data.round_number;
  gameState.status = data.status || 'waiting';
  gameState.currentMultiplier = data.live_multiplier || 1.00;
  document.getElementById('player-count').textContent = data.players_count || 0;
  updateUI();
});

// ============================================================================
// BET LOGIC
// ============================================================================

async function placeBet() {
  const amount = parseFloat(document.getElementById('bet-amount').value);
  
  if (!amount || amount < 10 || amount > 10000) {
    alert('Invalid bet amount');
    return;
  }
  
  if (gameState.status !== 'betting') {
    alert('Betting window is closed');
    return;
  }
  
  const response = await fetch('/crash/api/bet', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ amount })
  });
  
  const data = await response.json();
  
  if (data.success) {
    gameState.playerBetId = data.bet_id;
    gameState.playerBetAmount = amount;
    gameState.playerStatus = 'active';
    gameState.autoCashoutMultiplier = parseFloat(
      document.getElementById('auto-cashout-multiplier').value
    ) || null;
    
    updateUI();
    updateBalance(data.balance);
    
    // Clear input
    document.getElementById('bet-amount').value = '';
  } else {
    alert('Bet failed: ' + data.error);
  }
}

async function cashout() {
  if (gameState.playerStatus !== 'active') {
    alert('No active bet to cash out');
    return;
  }
  
  const response = await fetch('/crash/api/cashout', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({})
  });
  
  const data = await response.json();
  
  if (data.success) {
    gameState.playerStatus = 'cashed_out';
    
    // Show win notification
    showNotification(`🎉 Cashed out at ${gameState.currentMultiplier.toFixed(2)}x! +${formatMoney(data.profit)}`, 'success');
    
    gameState.stats.wins++;
    gameState.stats.totalWon += data.profit;
    if (gameState.currentMultiplier > gameState.stats.bestMultiplier) {
      gameState.stats.bestMultiplier = gameState.currentMultiplier;
    }
    
    updateUI();
    updateBalance(data.balance);
    updateStats();
    
    // Add to recent bets
    gameState.recentBets.unshift({
      amount: gameState.playerBetAmount,
      payout: data.payout,
      status: 'won',
      multiplier: gameState.currentMultiplier
    });
    updateRecentBets();
  } else {
    alert('Cashout failed: ' + data.error);
  }
}

function showNotification(message, type = 'info') {
  const notification = document.createElement('div');
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#0ea5e9'};
    color: white;
    padding: 1rem 1.5rem;
    border-radius: 8px;
    font-weight: 600;
    z-index: 9999;
    animation: slideIn 0.3s ease-out;
  `;
  notification.textContent = message;
  document.body.appendChild(notification);
  
  setTimeout(() => notification.remove(), 3000);
}

// ============================================================================
// EVENT LISTENERS
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
  initChart();
  
  // Fetch initial balance
  fetch('/crash')
    .then(r => r.text())
    .then(html => {
      const match = html.match(/balance[^>]*>([^<]+)/);
      if (match) {
        updateBalance(parseFloat(match[1]) || 0);
      }
    });
  
  // Place bet button
  document.getElementById('bet-button').addEventListener('click', placeBet);
  
  // Cashout button
  document.getElementById('cashout-button').addEventListener('click', cashout);
  
  // Preset buttons
  document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.getElementById('bet-amount').value = btn.dataset.amount;
      document.getElementById('bet-amount').focus();
    });
  });
  
  // Enter to place bet
  document.getElementById('bet-amount').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') placeBet();
  });
  
  // Fetch stats
  fetch('/crash/api/stats')
    .then(r => r.json())
    .then(stats => {
      gameState.stats.totalWagered = stats.total_wagered;
      gameState.stats.totalWon = stats.total_won;
      gameState.stats.wins = stats.win_count;
      gameState.stats.losses = stats.loss_count;
      gameState.stats.bestMultiplier = stats.best_multiplier || 0;
      updateStats();
    });
  
  // Fetch history
  fetch('/crash/api/history?limit=10')
    .then(r => r.json())
    .then(bets => {
      gameState.recentBets = bets.map(b => ({
        amount: b.amount,
        payout: b.payout,
        status: b.status,
        multiplier: b.cashout_at || gameState.crashPoint
      }));
      updateRecentBets();
    });
  
  updateUI();
});

// Add CSS animation for notifications
const style = document.createElement('style');
style.textContent = `
  @keyframes slideIn {
    from {
      transform: translateX(400px);
      opacity: 0;
    }
    to {
      transform: translateX(0);
      opacity: 1;
    }
  }
`;
document.head.appendChild(style);
