/*
   nslcd-server.c - server socket routines

   Copyright (C) 2006 West Consulting
   Copyright (C) 2006 Arthur de Jong

   This library is free software; you can redistribute it and/or
   modify it under the terms of the GNU Library General Public
   License as published by the Free Software Foundation; either
   version 2 of the License, or (at your option) any later version.

   This library is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
   Library General Public License for more details.

   You should have received a copy of the GNU Library General Public
   License along with this library; if not, write to the Free
   Software Foundation, Inc., 51 Franklin St, Fifth Floor, Boston,
   MA 02110-1301 USA
*/

#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <malloc.h>
#include <stdio.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <errno.h>
#include <fcntl.h>

#include "nslcd-server.h"
#include "log.h"


/* returns a socket ready to answer requests from the client,
   return <0 on error */
int nslcd_server_open(void)
{
  int sock;
  /*int flag;*/
  struct sockaddr_un addr;

  /* create a socket */
  if ( (sock=socket(PF_UNIX,SOCK_STREAM,0))<0 )
  {
    log_log(LOG_ERR,"cannot create socket: %s",strerror(errno));
    exit(1);
  }

  /* create socket address structure */
  addr.sun_family=AF_UNIX;
  strcpy(addr.sun_path,NSLCD_SOCKET);
  
  /* unlink to socket */
  if (unlink(NSLCD_SOCKET)<0)
  {
    log_log(LOG_DEBUG,"unlink() of "NSLCD_SOCKET" failed (ignored): %s",
            strerror(errno));
  }

  /* bind to the socket */
  if (bind(sock,(struct sockaddr *)&addr,sizeof(struct sockaddr_un))<0)
  {
    log_log(LOG_ERR,"bind() to "NSLCD_SOCKET" failed: %s",
            strerror(errno));
    if (close(sock))
      log_log(LOG_WARNING,"problem closing socket: %s",strerror(errno));
    exit(1);
  }

#ifdef NONBLOCKING
  /* we are going to block for now and implement threading later on */
  /* do not block on accept() */
  if ((flag=fcntl(sock,F_GETFL,0))<0)
  {
    log_log(LOG_ERR,"fctnl(F_GETFL) failed: %s",strerror(errno));
    if (close(sock))
      log_log(LOG_WARNING,"problem closing socket: %s",strerror(errno));
    exit(1);
  }
  if (fcntl(sock,F_SETFL,flag|O_NONBLOCK)<0)
  {
    log_log(LOG_ERR,"fctnl(F_SETFL,O_NONBLOCK) failed: %s",strerror(errno));
    if (close(sock))
      log_log(LOG_WARNING,"problem closing socket: %s",strerror(errno));
    exit(1);
  }
#endif /* NONBLOCKING */

  /* close the file descriptor on exit */
  if (fcntl(sock,F_SETFD,FD_CLOEXEC)<0)
  {
    log_log(LOG_ERR,"fctnl(F_SETFL,O_NONBLOCK) failed: %s",strerror(errno));
    if (close(sock))
      log_log(LOG_WARNING,"problem closing socket: %s",strerror(errno));
    exit(1);
  }

#ifdef DONT_FOR_NOW
  /* Set permissions for the socket.  */
  chmod (_PATH_NSCDSOCKET, DEFFILEMODE);
#endif /* DONT_FOR_NOW */

  /* start listening for connections */
  if (listen(sock,SOMAXCONN)<0)
  {
    log_log(LOG_ERR,"listen() failed: %s",strerror(errno));
    if (close(sock))
      log_log(LOG_WARNING,"problem closing socket: %s",strerror(errno));
    exit(1);
  }

  /* we're done */
  return sock;
}

/* redifine the ERROR_OUT mechanism */
#undef ERROR_OUT_READERROR
#define ERROR_OUT_READERROR(fp) \
  fclose(fp); \
  log_log(LOG_DEBUG,"error reading from stream: %s",strerror(errno)); \
  return;
  
/* read a request message, returns <0 in case of errors,
   this function closes the socket */
void nslcd_server_handlerequest(int sock)
{
  int32_t tmpint32;
  FILE *fp;
  /* create a stream object */
  if ((fp=fdopen(sock,"w+"))==NULL)
  {
    close(sock);
    return;
  }
  /* read the protocol version */
  READ_TYPE(fp,tmpint32,int32_t);
  if (tmpint32 != NSLCD_VERSION)
  {
    fclose(fp);
    log_log(LOG_DEBUG,"wrong nslcd version id (%d)",(int)tmpint32);
    return;
  }
  /* read the request type */
  READ_TYPE(fp,tmpint32,int32_t);
  /* handle request */
  switch (tmpint32)
  {
    case NSLCD_RT_GETPWBYNAME: nslcd_getpwnam(fp); break;
    case NSLCD_RT_GETPWBYUID:  nslcd_getpwuid(fp); break;
    case NSLCD_RT_GETPWALL:    nslcd_getpwall(fp); break;
    default:
      log_log(LOG_DEBUG,"invalid request id (%d)",(int)tmpint32);
      break;
  }
  /* we're done with the request */
  fclose(fp);  
  return;
}