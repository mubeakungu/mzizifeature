// Aviator Game - Client-side logic

class AviatorGame extends GameClient {
    constructor(gameType, gameConfig) {
        super(gameType, gameConfig);
        this.particles = [];
        this.setupAviatorUI();
        this.startAnimationLoop();
    }
    
    setupAviatorUI() {
        // Aviator-specific setup
        this.planeIcon = document.getElementById('plane-icon');
        this.animationId = null;
    }
    
    drawGameFrame(multiplier) {
        const { canvas, ctx } = this;
        
        // Draw sky background with gradient
        const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
        gradient.addColorStop(0, '#87CEEB');  // Light blue
        gradient.addColorStop(1, '#E0FFFF');  // Cyan
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        // Draw clouds at different depths
        this.drawClouds(multiplier);
        
        // Draw airplane
        const altitudePercent = Math.min((multiplier - 1) / (this.gameConfig.max_multiplier - 1), 1);
        const planeY = canvas.height * 0.9 - (altitudePercent * canvas.height * 0.7);
        this.drawAirplane(canvas.width / 2, planeY, multiplier);
        
        // Draw altitude info
        this.drawAltitudeInfo(canvas, multiplier);
        
        // Draw flight trail
        this.drawFlightTrail(canvas, multiplier);
    }
    
    drawClouds(multiplier) {
        const { canvas, ctx } = this;
        const cloudSpeed = multiplier * 0.5;
        
        // Simple cloud pattern
        const clouds = [
            { x: 100, y: 100, size: 1 },
            { x: 400, y: 200, size: 1.2 },
            { x: 700, y: 150, size: 0.9 },
            { x: 150, y: 350, size: 1.1 },
            { x: 600, y: 300, size: 1 }
        ];
        
        ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
        
        clouds.forEach(cloud => {
            const x = cloud.x % canvas.width;
            // Simple cloud shape (two circles)
            ctx.beginPath();
            ctx.arc(x, cloud.y, 30 * cloud.size, 0, Math.PI * 2);
            ctx.arc(x + 25 * cloud.size, cloud.y, 35 * cloud.size, 0, Math.PI * 2);
            ctx.arc(x + 50 * cloud.size, cloud.y, 30 * cloud.size, 0, Math.PI * 2);
            ctx.fill();
        });
    }
    
    drawAirplane(x, y, multiplier) {
        const { ctx } = this;
        ctx.save();
        ctx.translate(x, y);
        
        // Fuselage (body)
        ctx.fillStyle = '#2196F3';
        ctx.fillRect(-20, -8, 40, 16);
        
        // Cockpit
        ctx.fillStyle = '#FFB74D';
        ctx.beginPath();
        ctx.arc(15, 0, 5, 0, Math.PI * 2);
        ctx.fill();
        
        // Wings
        ctx.fillStyle = '#1976D2';
        ctx.fillRect(-35, -3, 70, 6);
        
        // Tail wings
        ctx.fillRect(-25, -8, 10, 16);
        
        // Flame effect
        if (multiplier > 1.5) {
            ctx.fillStyle = `rgba(255, 165, 0, ${Math.min((multiplier - 1) / 5, 1)})`;
            ctx.beginPath();
            ctx.moveTo(-20, -4);
            ctx.lineTo(-20, 4);
            ctx.lineTo(-20 - (multiplier * 5), 0);
            ctx.fill();
        }
        
        ctx.restore();
    }
    
    drawAltitudeInfo(canvas, multiplier) {
        const { ctx } = this;
        
        // Altitude meter on left side
        const meterX = 20;
        const meterY = 80;
        const meterHeight = 200;
        
        // Background
        ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
        ctx.fillRect(meterX, meterY, 30, meterHeight);
        
        // Altitude fill
        const altPercent = Math.min((multiplier - 1) / (this.gameConfig.max_multiplier - 1), 1);
        ctx.fillStyle = '#4CAF50';
        ctx.fillRect(meterX, meterY + meterHeight - (altPercent * meterHeight), 30, altPercent * meterHeight);
        
        // Border
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.strokeRect(meterX, meterY, 30, meterHeight);
        
        // Altitude text
        ctx.fillStyle = '#000';
        ctx.font = 'bold 16px Arial';
        ctx.textAlign = 'left';
        ctx.fillText(`${(multiplier * 100).toFixed(0)}m`, meterX + 40, meterY + 20);
    }
    
    drawFlightTrail(canvas, multiplier) {
        // Optional: draw a trail behind the plane
    }
    
    startAnimationLoop() {
        const animate = () => {
            // Continuous animation updates
            this.animationId = requestAnimationFrame(animate);
        };
        animate();
    }
    
    playCrashAnimation() {
        this.multiplierDisplay.style.animation = 'shake 0.6s ease-in-out';
        this.multiplierDisplay.classList.add('crashed');
        this.audioManager?.playSound('crash');
    }
}
