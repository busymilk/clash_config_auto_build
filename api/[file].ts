import type { VercelRequest, VercelResponse } from '@vercel/node';
import path from 'path';
import fs from 'fs';

export default function handler(req: VercelRequest, res: VercelResponse) {
  // 1. 从 Vercel 环境变量中获取预设的访问密码
  const secretToken = process.env.ACCESS_TOKEN;
  // 2. 从请求的 URL 查询参数中获取用户提供的密码
  const providedToken = req.query.token as string;
  // 3. 从请求路径中获取文件名 (e.g., 'config_us.yaml')
  const requestedFile = req.query.file as string;

  // 4. 检查服务器是否配置了密码
  if (!secretToken) {
    return res.status(500).send('Server configuration error: ACCESS_TOKEN is not set.');
  }

  // 5. 验证用户提供的密码
  if (providedToken !== secretToken) {
    return res.status(401).send('Unauthorized: Invalid or missing token.');
  }

  // 6. 验证文件名是否有效，防止路径遍历攻击
  if (!requestedFile || !requestedFile.endsWith('.yaml') || requestedFile.includes('..')) {
    return res.status(400).send('Bad Request: Invalid file name.');
  }

  // 7. 构建文件的绝对路径
  // Vercel 在构建时会将项目文件放在 /var/task/ 目录下
  const filePath = path.join(process.cwd(), 'config', requestedFile);

  // 8. 读取并返回文件内容
  try {
    if (fs.existsSync(filePath)) {
      const fileContent = fs.readFileSync(filePath, 'utf-8');
      res.setHeader('Content-Type', 'text/yaml; charset=utf-8');
      res.status(200).send(fileContent);
    } else {
      res.status(404).send('Not Found');
    }
  } catch (error) {
    console.error(error);
    res.status(500).send('Internal Server Error');
  }
}
