(() => {
  'use strict';
  // ปรับดาวตรงนี้: speed = ความเร็ว, depth = ช่วงมืด–สว่าง (0–1),
  // brightness = ความสว่าง, glow = แสงฟุ้ง, density = พื้นที่ต่อดาว (ลดแล้วดาวมากขึ้น)
  const SKY_SETTINGS = {
    speed: 1.6,
    depth: 0.92,
    brightness: 4.2,
    glow: 0.65,
    density: 6000,
    // วงดาวแบบภาพอ้างอิง: เปลี่ยน orbitEnabled เป็น false เพื่อกลับไปใช้ดาวเดิม
    orbitEnabled: true,
    orbitSpeed: 1,       // เพิ่มแล้วหมุนเร็วขึ้น
    orbitOpacity: 0.35, // ความชัดของวงดาว (0–1)
  };
  const canvas = document.querySelector('#starfield');
  const context = canvas && canvas.getContext('2d');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let paused = reducedMotion.matches;

  if (context) {
    let stars = [];
    let width = 0;
    let height = 0;
    let frame = 0;
    let lastTime = 0;
    let orbitTime = 0;
    let orbitLayers = [];
    let orbitRadius = 0;

    // Draw the ornaments once, then rotate the cached layers each frame.
    // Result pages inherit the deity's color; the home page uses warm bronze.
    function buildOrbits(random) {
      orbitLayers = [];
      if (!SKY_SETTINGS.orbitEnabled) return;
      orbitRadius = Math.min(width < 650 ? width * 0.8 : width * 0.48, height * 0.58, 570);
      const tint = document.body.hasAttribute('data-deity')
        ? getComputedStyle(document.body).getPropertyValue('--deity-rgb').trim()
        : '234, 181, 132';
      const ratio = Math.min(window.devicePixelRatio || 1, 1.5);
      const extent = orbitRadius * 1.12;
      const unit = Math.max(0.6, orbitRadius / 490);
      const mobile = width < 650;

      for (let layer = 0; layer < 2; layer++) {
        const direction = layer ? -1 : 1;
        const surface = document.createElement('canvas');
        surface.width = surface.height = Math.ceil(extent * 2 * ratio);
        const ink = surface.getContext('2d');
        if (!ink) continue;
        ink.setTransform(ratio, 0, 0, ratio, extent * ratio, extent * ratio);

        // Uneven dotted arcs taper into larger beads, like little comet paths.
        const trails = mobile ? 16 : 25;
        for (let trail = 0; trail < trails; trail++) {
          const radius = orbitRadius * (0.43 + random() * 0.55);
          const start = random() * Math.PI * 2;
          const length = 0.1 + random() * 0.28;
          const beads = 9 + Math.floor(random() * 13);
          const headSize = (1.9 + Math.pow(random(), 3) * 5) * unit;
          const beadSize = Math.min(headSize, radius * length / (beads - 1) * 0.38);
          const opacity = 0.36 + random() * 0.5;
          for (let bead = 0; bead < beads; bead++) {
            const progress = bead / (beads - 1);
            const angle = start + direction * progress * length;
            const drift = (progress - 0.5) * orbitRadius * 0.025;
            const size = 0.15 * unit + Math.pow(progress, 1.7) * beadSize;
            ink.beginPath();
            ink.arc(Math.cos(angle) * (radius + drift), Math.sin(angle) * (radius + drift), size, 0, Math.PI * 2);
            ink.fillStyle = `rgba(${tint},${opacity * (0.3 + progress * 0.7)})`;
            ink.fill();
          }
          if (trail % 3 === 0) {
            const angle = start + direction * (length + headSize * 1.8 / radius);
            const distance = radius + orbitRadius * 0.0125;
            ink.beginPath();
            ink.arc(Math.cos(angle) * distance, Math.sin(angle) * distance, headSize, 0, Math.PI * 2);
            ink.fillStyle = `rgba(${tint},${opacity})`;
            ink.fill();
          }
        }

        for (let speck = 0; speck < (mobile ? 55 : 95); speck++) {
          const angle = random() * Math.PI * 2;
          const radius = orbitRadius * (0.39 + random() * 0.65);
          ink.beginPath();
          ink.arc(Math.cos(angle) * radius, Math.sin(angle) * radius, (0.35 + random()) * unit, 0, Math.PI * 2);
          ink.fillStyle = `rgba(${tint},${0.2 + random() * 0.45})`;
          ink.fill();
        }

        // A few small sunbursts and a crescent echo the reference illustration.
        for (let sun = 0; sun < 2; sun++) {
          const angle = (layer * 1.4 + sun * 2.6 + 0.3);
          const radius = orbitRadius * (sun ? 0.73 : 0.98);
          ink.save();
          ink.translate(Math.cos(angle) * radius, Math.sin(angle) * radius);
          ink.rotate(angle);
          ink.beginPath();
          for (let point = 0; point < 20; point++) {
            const theta = point * Math.PI / 10;
            const reach = (point % 2 ? 4 : 8) * unit;
            const x = Math.cos(theta) * reach;
            const y = Math.sin(theta) * reach;
            if (point === 0) ink.moveTo(x, y); else ink.lineTo(x, y);
          }
          ink.closePath();
          ink.fillStyle = `rgba(${tint},0.8)`;
          ink.fill();
          ink.restore();
        }

        if (layer === 0) {
          ink.save();
          ink.translate(-orbitRadius * 0.7, orbitRadius * 0.59);
          ink.rotate(-0.45);
          ink.beginPath();
          ink.arc(0, 0, 14 * unit, 0, Math.PI * 2);
          ink.fillStyle = `rgba(${tint},0.85)`;
          ink.fill();
          ink.globalCompositeOperation = 'destination-out';
          ink.beginPath();
          ink.arc(5 * unit, -5 * unit, 13 * unit, 0, Math.PI * 2);
          ink.fill();
          ink.restore();
        }

        // Fade the inner edge so the text and deity remain easy to read.
        ink.globalCompositeOperation = 'destination-in';
        const fade = ink.createRadialGradient(0, 0, orbitRadius * 0.28, 0, 0, extent);
        fade.addColorStop(0, 'rgba(0,0,0,0)');
        fade.addColorStop(0.23, 'rgba(0,0,0,0.5)');
        fade.addColorStop(0.5, 'rgba(0,0,0,1)');
        fade.addColorStop(0.83, 'rgba(0,0,0,0.8)');
        fade.addColorStop(1, 'rgba(0,0,0,0)');
        ink.fillStyle = fade;
        ink.fillRect(-extent, -extent, extent * 2, extent * 2);
        orbitLayers.push({ surface, extent, direction, period: layer ? 240000 : 155000 });
      }
    }

    function drawOrbits() {
      if (!SKY_SETTINGS.orbitEnabled || !orbitLayers.length) return;
      context.save();
      context.translate(width / 2, height * 0.51);
      context.globalAlpha = SKY_SETTINGS.orbitOpacity;
      for (let i = 0; i < orbitLayers.length; i++) {
        const { surface, extent, direction, period } = orbitLayers[i];
        context.save();
        context.rotate(i * 0.65 + direction * orbitTime / period * Math.PI * 2 * SKY_SETTINGS.orbitSpeed);
        context.drawImage(surface, -extent, -extent, extent * 2, extent * 2);
        context.restore();
      }
      context.restore();
    }

    function draw(time) {
      context.clearRect(0, 0, width, height);
      drawOrbits();
      for (const star of stars) {
        const wave = (1 + Math.sin(time * star.speed * SKY_SETTINGS.speed + star.phase)) / 2;
        const pulse = paused ? 0.55 : 1 - SKY_SETTINGS.depth + Math.pow(wave, 1.8) * SKY_SETTINGS.depth;
        const alpha = Math.min(1, pulse * star.opacity * SKY_SETTINGS.brightness);
        context.beginPath();
        context.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
        context.fillStyle = `rgba(${star.warm ? '236,200,164' : '199,219,245'},${alpha})`;
        context.fill();
        if (star.radius > 1.05) {
          const radius = 3 + pulse * 3;
          const glow = context.createRadialGradient(star.x, star.y, 0, star.x, star.y, radius);
          glow.addColorStop(0, `rgba(170,194,220,${alpha * SKY_SETTINGS.glow})`);
          glow.addColorStop(1, 'rgba(170,194,220,0)');
          context.fillStyle = glow;
          context.fillRect(star.x - radius, star.y - radius, radius * 2, radius * 2);
        }
      }
    }

    function animate(time) {
      if (time - lastTime > 40) {
        if (lastTime) orbitTime += Math.min(time - lastTime, 80);
        draw(time);
        lastTime = time;
      }
      frame = requestAnimationFrame(animate);
    }

    function refresh() {
      cancelAnimationFrame(frame);
      lastTime = 0;
      draw(performance.now());
      if (!paused && !document.hidden) frame = requestAnimationFrame(animate);
    }

    function resize() {
      width = window.innerWidth;
      height = window.innerHeight;
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      // Seeded positions prevent the sky from jumping each time it is resized.
      let seed = 2710;
      const random = () => {
        seed = (seed * 16807) % 2147483647;
        return (seed - 1) / 2147483646;
      };
      stars = Array.from({ length: Math.min(300, Math.max(65, Math.round(width * height / SKY_SETTINGS.density))) }, () => ({
        x: random() * width, y: random() * height,
        radius: 0.35 + random() * 0.95,
        opacity: 0.35 + random() * 0.65,
        speed: 0.0008 + random() * 0.0011,
        phase: random() * Math.PI * 2, warm: random() > 0.85,
      }));
      buildOrbits(random);
      refresh();
    }

    reducedMotion.addEventListener('change', event => {
      paused = event.matches;
      refresh();
    });
    window.addEventListener('resize', resize);
    document.addEventListener('visibilitychange', refresh);
    resize();
  }

  const form = document.querySelector('.birth-form');
  if (form) {
    const button = form.querySelector('button[type="submit"]');
    form.addEventListener('submit', () => {
      button.disabled = true;
      button.querySelector('.submit-label').textContent = 'กำลังอ่านดวงดาว…';
    });
    window.addEventListener('pageshow', () => {
      button.disabled = false;
      button.querySelector('.submit-label').textContent = 'เปิดดวงชาตาของฉัน';
    });
  }
})();
