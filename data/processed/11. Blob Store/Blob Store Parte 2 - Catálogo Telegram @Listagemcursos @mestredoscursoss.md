# 11. Blob Store

## Resumo
O vídeo aprofunda o conceito e o funcionamento das Blob Stores, focando em como lidar com armazenamento de grandes objetos binários, estratégias de chaves, segurança com Presigned URLs, particionamento e otimização de uploads.

## Tópicos Principais
- Conceito de Blob Store
- Modelos de Dados e Metadados
- Presigned URLs para Segurança e Acesso
- Particionamento e Multipart Uploads

## Código e Timestamps
### Exemplo de Estrutura de Chave
- **Timestamp:** 01:32
- **Linguagem:** typescript
```typescript
user 123
profile picture.png
```

### Tabela SQL com Referência
- **Timestamp:** 02:45
- **Linguagem:** sql
```sql
CREATE TABLE users (
  name, email,
  profile_picture_url
);
```