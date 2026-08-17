document.addEventListener('DOMContentLoaded', () => {
  const configEl = document.getElementById('analysis-config');
  if (!configEl) return;

  const jobId = configEl.dataset.jobId || '';
  const currentStatus = configEl.dataset.status || '';

  // ① 解析中ポーリング
  if (currentStatus === 'processing') {
    const progressBar = document.getElementById('progressBar');
    const progressPercent = document.getElementById('progressPercent');

    const pollTimer = setInterval(async () => {
      try {
        const res = await fetch(`/api/jobs/${jobId}`);
        if (!res.ok) return;

        const data = await res.json();
        const progress = data.progress || 0;
        if (progressBar) progressBar.style.width = `${progress}%`;
        if (progressPercent) progressPercent.textContent = `${progress}%`;

        if (data.status === 'completed' || progress >= 100) {
          clearInterval(pollTimer);
          setTimeout(() => window.location.reload(), 500);
        }
      } catch (err) {
        console.error('Polling error:', err);
      }
    }, 1000);

    return;
  }

  // ② 解析完了後のプレイヤー & グラフ制御
  const framesDataEl = document.getElementById('frames-data');
  const frames = framesDataEl ? JSON.parse(framesDataEl.textContent || '[]') : [];

  const bmModelsDataEl = document.getElementById('benchmark-models-data');
  const benchmarkModels = bmModelsDataEl ? JSON.parse(bmModelsDataEl.textContent || '[]') : [];

  const analysisData = {
    duration_ms: parseFloat(configEl.dataset.durationMs || '3500'),
    frames: frames,
    current_angle: parseFloat(configEl.dataset.currentAngle || '10.5'),
  };

  const userVideo = document.getElementById('userVideoPlayer');
  const benchVideo = document.getElementById('benchVideoPlayer');
  const benchFrame = document.getElementById('benchFrame');
  const videoGrid = document.getElementById('videoGrid');
  const benchSelector = document.getElementById('benchmarkSelector');
  const playBtn = document.getElementById('playPauseBtn');
  const seekBar = document.getElementById('seekBar');
  const curEl = document.getElementById('currentAngle');
  const benchEl = document.getElementById('benchmarkAngle');
  const curTimeEl = document.getElementById('currentTimeText');
  const totalTimeEl = document.getElementById('totalTimeText');

  let currentBenchmark = null;
  let swingChart = null;

  function msToTimeString(ms) {
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    const centiseconds = Math.floor((ms % 1000) / 100);
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}.${centiseconds}`;
  }

  function updateDisplayValues(frameIndex) {
    let curAngle = analysisData.current_angle;
    if (analysisData.frames.length > 0) {
      const idx = Math.max(0, Math.min(analysisData.frames.length - 1, Math.round(frameIndex)));
      curAngle = analysisData.frames[idx].spine_angle || curAngle;
    }
    if (curEl) curEl.textContent = `${curAngle.toFixed(1)}°`;

    if (currentBenchmark && currentBenchmark.frames && currentBenchmark.frames.length > 0) {
      const totalUserFrames = analysisData.frames.length || 30;
      const ratio = frameIndex / Math.max(1, totalUserFrames - 1);
      const bIdx = Math.min(currentBenchmark.frames.length - 1, Math.floor(ratio * currentBenchmark.frames.length));
      const bAngle = currentBenchmark.frames[bIdx].spine_angle ?? currentBenchmark.target_angle;
      if (benchEl) benchEl.textContent = `${bAngle.toFixed(1)}°`;
    }

    if (userVideo && !isNaN(userVideo.currentTime) && curTimeEl) {
      curTimeEl.textContent = msToTimeString(userVideo.currentTime * 1000);
    }
  }

  function togglePlayPause() {
    const isPlaying = playBtn?.textContent.includes('停止');
    if (isPlaying) {
      if (userVideo) userVideo.pause();
      if (benchVideo) benchVideo.pause();
      if (playBtn) playBtn.textContent = '▶ 再生';
    } else {
      if (userVideo) userVideo.play().catch(() => {});
      if (benchVideo && benchFrame && benchFrame.style.display !== 'none') {
        benchVideo.play().catch(() => {});
      }
      if (playBtn) playBtn.textContent = '⏸ 停止';
    }
  }

  function frameStep(direction) {
    if (!userVideo || isNaN(userVideo.duration)) return;
    userVideo.pause();
    if (benchVideo) benchVideo.pause();
    if (playBtn) playBtn.textContent = '▶ 再生';

    const stepSec = 1.0 / 30.0;
    userVideo.currentTime = Math.max(0, Math.min(userVideo.duration, userVideo.currentTime + direction * stepSec));
    if (benchVideo && !isNaN(benchVideo.duration)) {
      const pct = userVideo.currentTime / userVideo.duration;
      benchVideo.currentTime = pct * benchVideo.duration;
    }
  }

  if (userVideo) {
    userVideo.addEventListener('timeupdate', () => {
      if (!userVideo.duration) return;
      const pct = (userVideo.currentTime / userVideo.duration) * 100;
      if (seekBar) seekBar.value = pct;

      if (benchVideo && benchVideo.duration && !benchVideo.seeking && benchFrame && benchFrame.style.display !== 'none') {
        const targetTime = (pct / 100) * benchVideo.duration;
        if (Math.abs(benchVideo.currentTime - targetTime) > 0.08) {
          benchVideo.currentTime = targetTime;
        }
      }

      const totalFrames = analysisData.frames.length || 30;
      const frameIdx = (userVideo.currentTime / userVideo.duration) * (totalFrames - 1);
      updateDisplayValues(frameIdx);
    });

    userVideo.addEventListener('ended', () => {
      if (benchVideo) benchVideo.pause();
      if (playBtn) playBtn.textContent = '▶ 再生';
    });

    userVideo.addEventListener('loadedmetadata', () => {
      const totalMs = userVideo.duration * 1000;
      if (totalTimeEl) totalTimeEl.textContent = msToTimeString(totalMs);
      updateDisplayValues(0);
    });
  }

  playBtn?.addEventListener('click', togglePlayPause);
  document.getElementById('frameBackBtn')?.addEventListener('click', () => frameStep(-1));
  document.getElementById('frameForwardBtn')?.addEventListener('click', () => frameStep(1));

  seekBar?.addEventListener('input', (e) => {
    const pct = parseFloat(e.target.value) / 100;
    if (userVideo && !isNaN(userVideo.duration)) userVideo.currentTime = pct * userVideo.duration;
    if (benchVideo && !isNaN(benchVideo.duration)) benchVideo.currentTime = pct * benchVideo.duration;
  });

  document.querySelectorAll('.speed-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.speed-btn').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      const speed = parseFloat(e.target.dataset.speed);
      if (userVideo) userVideo.playbackRate = speed;
      if (benchVideo) benchVideo.playbackRate = speed;
    });
  });

  function updateBenchmarkUI() {
    const selectedId = benchSelector ? benchSelector.value : '';
    currentBenchmark = benchmarkModels.find(m => m.id === selectedId) || null;

    if (currentBenchmark && currentBenchmark.video_url && benchVideo && benchFrame && videoGrid) {
      videoGrid.style.gridTemplateColumns = '1fr 1fr';
      benchFrame.style.display = 'block';
      benchVideo.src = currentBenchmark.video_url;
      benchVideo.load();
      if (benchEl) benchEl.textContent = `${(currentBenchmark.target_angle || 0).toFixed(1)}°`;
    } else if (benchFrame && videoGrid) {
      videoGrid.style.gridTemplateColumns = '1fr';
      benchFrame.style.display = 'none';
      if (benchVideo) benchVideo.src = '';
      currentBenchmark = null;
    }

    if (swingChart) {
      if (currentBenchmark) {
        const userFrameCount = analysisData.frames.length || 30;
        const benchFrames = currentBenchmark.frames || [];

        let benchCurve = [];
        if (benchFrames.length > 0) {
          benchCurve = Array.from({ length: userFrameCount }, (_, i) => {
            const ratio = i / Math.max(1, userFrameCount - 1);
            const bIdx = Math.min(benchFrames.length - 1, Math.floor(ratio * benchFrames.length));
            return benchFrames[bIdx].spine_angle ?? currentBenchmark.target_angle ?? 38.0;
          });
        } else {
          benchCurve = Array(userFrameCount).fill(currentBenchmark.target_angle || 38.0);
        }

        if (swingChart.data.datasets.length > 1) {
          swingChart.data.datasets[1].data = benchCurve;
          swingChart.data.datasets[1].label = `お手本 (${currentBenchmark.name})`;
        } else {
          swingChart.data.datasets.push({
            label: `お手本 (${currentBenchmark.name})`,
            data: benchCurve,
            borderColor: '#34d399',
            borderDash: [4, 4],
            pointRadius: 2,
            borderWidth: 2,
          });
        }
      } else {
        if (swingChart.data.datasets.length > 1) {
          swingChart.data.datasets.pop();
        }
      }
      swingChart.update();
    }
  }

  benchSelector?.addEventListener('change', updateBenchmarkUI);

  // 時系列グラフ初期化 & クリック時2画面同時ジャンプ
  const chartEl = document.getElementById('swingChart');
  if (chartEl && window.Chart) {
    const ctx = chartEl.getContext('2d');
    const fList = analysisData.frames.length > 0 ? analysisData.frames : [{ spine_angle: analysisData.current_angle }];
    const labels = fList.map((_, i) => `${i}`);
    const myAngles = fList.map(f => f.spine_angle || 0);

    swingChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          {
            label: '体幹傾斜角度 (自分)',
            data: myAngles,
            borderColor: '#60a5fa',
            backgroundColor: 'rgba(96, 165, 250, 0.12)',
            fill: true,
            tension: 0.35,
            borderWidth: 2,
            pointRadius: 2,
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { labels: { color: '#cbd5e1', font: { size: 10 } } },
        },
        scales: {
          x: { ticks: { color: '#94a3b8', font: { size: 9 } }, grid: { color: '#334155' } },
          y: { ticks: { color: '#94a3b8', font: { size: 9 } }, grid: { color: '#334155' } },
        },
        onClick: (_, elements) => {
          if (elements.length > 0) {
            const index = elements[0].index;
            const ratio = index / Math.max(1, fList.length - 1);

            if (userVideo && !isNaN(userVideo.duration)) {
              userVideo.currentTime = ratio * userVideo.duration;
            }
            if (benchVideo && !isNaN(benchVideo.duration) && benchFrame && benchFrame.style.display !== 'none') {
              benchVideo.currentTime = ratio * benchVideo.duration;
            }
          }
        },
      },
    });
  }
});