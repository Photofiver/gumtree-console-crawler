import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { createServer } from 'node:http';
import { readFileSync } from 'node:fs';
import { z } from 'zod';
import { validateReceipt } from './validate.js';

const REPO='Photofiver/gumtree-console-crawler';
const TEMPLATE='ui://consult/handoff-v1.html';
const html=readFileSync(new URL('./widget.html',import.meta.url),'utf8');
const server=new McpServer({name:'github-google-ai-handoff',version:'0.1.0'},{capabilities:{tools:{},resources:{}}});
server.registerResource('handoff-widget',TEMPLATE,{},async()=>({contents:[{uri:TEMPLATE,mimeType:'text/html;profile=mcp-app',text:html,_meta:{ui:{csp:{connectDomains:['https://api.github.com']}}}}]}));
server.registerTool('open_consult_handoff',{description:'Open an active ChatGPT widget to monitor public Google AI consultation receipts on GitHub. Requires active widget; does not wake closed chats.',inputSchema:{issue:z.number().int().positive().default(293)},_meta:{ui:{resourceUri:TEMPLATE}}},async({issue})=>({content:[{type:'text',text:'Monitoring widget for GitHub issue #'+issue+'. It works only while open.'}],structuredContent:{issue,repository:REPO}}));
server.registerTool('get_consult_receipt',{description:'Read and validate the latest Google AI consultation receipt in a public GitHub issue.',inputSchema:{issue:z.number().int().positive()}},async({issue})=>{
 const url='https://api.github.com/repos/'+REPO+'/issues/'+issue;
 const headers={'Accept':'application/vnd.github+json','User-Agent':'consult-handoff-mcp'};
 const [ir,cr]=await Promise.all([fetch(url,{headers}),fetch(url+'/comments?per_page=100',{headers})]);
 if(!ir.ok||!cr.ok)throw new Error('GitHub HTTP '+ir.status+'/'+cr.status);
 const result=validateReceipt(await ir.json(),await cr.json());
 return {content:[{type:'text',text:JSON.stringify(result)}],structuredContent:result};
});
const http=createServer(async(req,res)=>{
 if(req.url!=='/mcp'){res.writeHead(404).end();return;}
 const transport=new StreamableHTTPServerTransport({sessionIdGenerator:undefined});
 res.on('close',()=>transport.close());
 try{await server.connect(transport);await transport.handleRequest(req,res);}catch(e){if(!res.headersSent)res.writeHead(500).end(String(e));}
});
http.listen(Number(process.env.PORT||3000),'0.0.0.0',()=>console.log('MCP listening'));
