const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

function run(cmd) {
    try { execSync(cmd, { stdio: 'ignore' }); } catch (e) {}
}

function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
}

async function main() {
    console.log('🧹 Killing processes locking release folder...');
    
    // Kill by name (common ones)
    run('taskkill /F /IM "Jarvis Assistant Portable.exe" /T');
    run('taskkill /F /IM "Jarvis Assistant.exe" /T');
    run('taskkill /F /IM "jarvis-backend.exe" /T');
    run('taskkill /F /IM "electron.exe" /T');
    
    // Kill anything running FROM the release-fix folder
    run('wmic process where "ExecutablePath like \'%release-fix%\'" delete');
    run('wmic process where "ExecutablePath like \'%JarvisInstaller%\'" delete');
    
    // Wait for OS to release file handles
    await sleep(2000);
    
    // Force delete with retries
    const dirs = [
        path.join(__dirname, '..', 'release-fix'),
        path.join(__dirname, '..', 'release-fix-temp'),
    ];
    
    for (const dir of dirs) {
        if (!fs.existsSync(dir)) continue;
        for (let i = 0; i < 5; i++) {
            try {
                fs.rmSync(dir, { recursive: true, force: true });
                console.log(`✅ Deleted ${path.basename(dir)}`);
                break;
            } catch (e) {
                if (i === 4) console.warn(`⚠️ Could not delete ${dir}: ${e.message}`);
                await sleep(1000);
            }
        }
    }
    
    console.log('✅ Cleanup done — starting build...');
}

main();
