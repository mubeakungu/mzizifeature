class JetXGame extends GameClient {
    constructor(gameType, gameConfig) {
        super(gameType, gameConfig);
        this.fuelAmount = 100;
        this.rocketX = 0;
        this.rocketY = 0;
    }
    
    drawGameFrame(multiplier) {
        const { canvas, ctx } = this;
        
        // Dark space background
        ctx.fillStyle = '#0a0e27';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        // Draw stars
        this.drawStars();
        
        // Calculate rocket position
        const altitudePercent = Math.min((multiplier - 1) / (this.gameConfig.max_multiplier - 1), 1);
        const rocketY = canvas.height * 0.85 - (altitudePercent * canvas.height * 0.7);
        
        // Draw rocket
        this.drawRocket(canvas.width / 2, rocketY);
        
        // Draw fuel gauge
        this.fuelAmount = 100 - (altitudePercent * 100);
        this.drawFuelGauge(canvas, this.fuelAmount);
        
        // Draw altitude readout
        ctx.fillStyle = '#00ff00';
        ctx.font = 'bold 36px Courier';
        ctx.textAlign = 'center';
        ctx.fillText(`${multiplier.toFixed(2)}x`, canvas.width / 2, 60);
    }
    
    drawRocket(x, y) {
        const { ctx } = this;
        
        ctx.save();
        ctx.translate(x, y);
        
        // Rocket body
        ctx.fillStyle = '#ff6b00';
        ctx.fillRect(-15, -40, 30, 60);
        
        // Rocket nose
        ctx.fillStyle = '#ffaa00';
        ctx.beginPath();
        ctx.moveTo(-8, -40);
        ctx.lineTo(8, -40);
        ctx.lineTo(0, -60);
        ctx.fill();
        
        // Fins
        ctx.fillStyle = '#ff4444';
        ctx.beginPath();
        ctx.moveTo(-15, 10);
        ctx.lineTo(-30, 20);
        ctx.lineTo(-15, 20);
        ctx.fill();
        
        ctx.beginPath();
        ctx.moveTo(15, 10);
        ctx.lineTo(30, 20);
        ctx.lineTo(15, 20);
        ctx.fill();
        
        // Flame
        ctx.fillStyle = 'rgba(255, 200, 0, 0.8)';
        ctx.beginPath();
        ctx.moveTo(-8, 20);
        ctx.lineTo(8, 20);
        ctx.lineTo(0, 50 + Math.random() * 20);
        ctx.fill();
        
        // Inner flame
        ctx.fillStyle = 'rgba(255, 50, 0, 0.6)';
        ctx.beginPath();
        ctx.moveTo(-5, 20);
        ctx.lineTo(5, 20);
        ctx.lineTo(0, 40);
        ctx.fill();
        
        ctx.restore();
    }
    
    drawFuelGauge(canvas, fuelPercent) {
        const { ctx } = this;
        
        const x = 20;
        const y = canvas.height - 100;
        const width = 150;
        const height = 30;
        
        // Background
        ctx.fillStyle = '#222';
        ctx.fillRect(x, y, width, height);
        
        // Fuel level
        const fuelColor = fuelPercent > 50 ? '#00ff00' : fuelPercent > 25 ? '#ffaa00' : '#ff3333';
        ctx.fillStyle = fuelColor;
        ctx.fillRect(x + 2, y + 2, (width - 4) * (fuelPercent / 100), height - 4);
        
        // Border
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.strokeRect(x, y, width, height);
        
        // Text
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 14px Arial';
        ctx.textAlign = 'center';
        ctx.fillText(`FUEL: ${fuelPercent.toFixed(0)}%`, x + width / 2, y + height + 20);
    }
    
    drawStars() {
        const { canvas, ctx } = this;
        ctx.fillStyle = 'white';
        
        // Fixed star pattern
        const stars = [
            [100, 50], [200, 100], [300, 30], [400, 80], [500, 60],
            [600, 40], [700, 90], [800, 50], [850, 120]
        ];
        
        stars.forEach(([x, y]) => {
            ctx.beginPath();
            ctx.arc(x, y, 1, 0, Math.PI * 2);
            ctx.fill();
        });
    }
    
    playCrashAnimation() {
        super.playCrashAnimation();
        this.multiplierDisplay.textContent = 'SYSTEM OVERLOAD!';
        this.multiplierDisplay.classList.add('crashed');
    }
}
