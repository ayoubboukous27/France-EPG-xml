const fs = require('fs');
const path = require('path');
const axios = require('axios');
const xml2js = require('xml2js');
const dayjs = require('dayjs');
const config = require('../data/programme-tv.net.config.js');
const channelsXmlFile = path.join(__dirname, '../data/programme-tv.net.channels.xml');

async function loadChannels() {
  const xmlData = fs.readFileSync(channelsXmlFile, 'utf-8');
  const parser = new xml2js.Parser();
  const result = await parser.parseStringPromise(xmlData);
  return result.channels.channel.map(ch => ({
    name: ch._,
    site_id: ch.$.site_id,
    xmltv_id: ch.$.xmltv_id || ch.$.site_id,
  }));
}

async function fetchEPG(channel, date) {
  const url = config.url({ date: dayjs(date), channel });
  try {
    const response = await axios.get(url, config.request);
    const programs = config.parser({ content: response.data, date: dayjs(date) });
    return programs.map(p => ({
      title: p.title,
      subtitle: p.subTitle,
      category: p.category,
      start: p.start.format('YYYYMMDDHHmmss Z'),
      stop: p.stop.format('YYYYMMDDHHmmss Z'),
      channel_id: channel.xmltv_id
    }));
  } catch (error) {
    console.error(`خطأ في سحب EPG للقناة ${channel.name}:`, error.message);
    return [];
  }
}

async function main() {
  const channels = await loadChannels();
  const date = new Date();
  const xmlBuilder = new xml2js.Builder({ headless: true, rootName: 'tv' });
  const xmlData = { channel: [], programme: [] };

  for (const channel of channels) {
    xmlData.channel.push({ $: { id: channel.xmltv_id }, display_name: channel.name });
    const epgPrograms = await fetchEPG(channel, date);
    epgPrograms.forEach(p => {
      const programme = { $: { start: p.start, stop: p.stop, channel: p.channel_id }, title: p.title };
      if (p.subtitle) programme.subtitle = p.subtitle;
      if (p.category) programme.category = p.category;
      xmlData.programme.push(programme);
    });
  }

  const epgDir = path.join(__dirname, '../epg');
  if (!fs.existsSync(epgDir)) fs.mkdirSync(epgDir);
  const fileName = `epg-${dayjs(date).format('YYYY-MM-DD')}.xml`;
  const outputFile = path.join(epgDir, fileName);
  fs.writeFileSync(outputFile, xmlBuilder.buildObject(xmlData), 'utf-8');
  console.log(`تم كتابة ملف EPG: ${outputFile}`);

  // Git push تلقائي
  const { execSync } = require('child_process');
  try {
    execSync('git config user.name "github-actions[bot]"');
    execSync('git config user.email "github-actions[bot]@users.noreply.github.com"');
    execSync(`git add epg/${fileName}`);
    execSync(`git commit -m "Update EPG for ${dayjs(date).format('YYYY-MM-DD')}"`);
    execSync('git push');
    console.log('تم رفع ملف EPG إلى الريبو بنجاح.');
  } catch (err) {
    console.log('لا توجد تغييرات جديدة للرفع أو حدث خطأ في Git:', err.message);
  }
}

main();
