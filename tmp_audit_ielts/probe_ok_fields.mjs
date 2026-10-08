// 检查所有导出函数的顶层 ok 字段 + 无参调用是否抛异常
import * as api from 'file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs';
const fns = Object.entries(api).filter(([k,v]) => typeof v === "function");
console.log("total exported functions:", fns.length);
console.log("names:", fns.map(([k])=>k).join(", "));
